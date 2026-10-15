from app.core.enums import PaymentMethod, PaymentStatus
from app.core.exceptions import (
    DuplicateIdempotencyKeyError,
    InvalidAmountError,
    InvalidInstallmentError,
    InvalidTransitionError,
    PaymentNotFoundError,
    UnknownPromoCodeError,
)
from app.models.billing import Payment, Tariff
from app.repositories.billing import BillingRepository


def calculate_price(price: int, promo_code: str | None) -> tuple[int, int]:
    if price < 0:
        raise InvalidAmountError("Price must be nonnegative")
    if promo_code is None:
        return price, 0
    if promo_code.upper() != "KVITTO10":
        raise UnknownPromoCodeError("Unknown promo code")

    discount = price * 10 // 100
    return price - discount, discount


def build_schedule(amount: int, months: int) -> list[int]:
    if amount < 0:
        raise InvalidAmountError("Amount must be nonnegative")
    if months not in {3, 6, 12}:
        raise InvalidInstallmentError("Installment months must be 3, 6 or 12")

    base, remainder = divmod(amount, months)
    return [base + (index < remainder) for index in range(months)]


ALLOWED_TRANSITIONS = {
    PaymentStatus.pending: {PaymentStatus.succeeded, PaymentStatus.failed},
    PaymentStatus.succeeded: {PaymentStatus.refunded},
}


def validate_transition(current: PaymentStatus, target: PaymentStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise InvalidTransitionError("Invalid payment status transition")


class BillingService:

    def __init__(self, repository: BillingRepository) -> None:
        self.repository = repository

    async def seed_tariffs(self) -> None:
        if not await self.repository.has_tariffs():
            await self.repository.add_tariffs(
                [
                    Tariff(title="basic", price=990000),
                    Tariff(title="standard", price=1990000),
                    Tariff(title="premium", price=2990000),
                ]
            )

    async def list_tariffs(self) -> list[Tariff]:
        return await self.repository.list_tariffs()

    async def create_payment(
        self,
        tariff_id: int,
        email: str,
        method: PaymentMethod,
        installment_months: int | None,
        promo_code: str | None,
        idempotency_key: str | None,
    ) -> tuple[Payment, bool]:
        if idempotency_key is not None:
            try:
                return await self.repository.get_payment_by_key(idempotency_key), False
            except PaymentNotFoundError:
                pass  # A missing key is handled by creating its first payment below.

        if method == PaymentMethod.installment:
            if installment_months not in {3, 6, 12}:
                raise InvalidInstallmentError("Installment months must be 3, 6 or 12")
        elif installment_months is not None:
            raise InvalidInstallmentError("Term is only allowed for installments")

        tariff = await self.repository.get_tariff(tariff_id)
        amount, discount = calculate_price(tariff.price, promo_code)
        payment = Payment(
            tariff_id=tariff.id,
            email=email.lower(),
            method=method,
            amount=amount,
            discount=discount,
            installment_months=installment_months,
            schedule=(
                build_schedule(amount, installment_months)
                if installment_months is not None
                else None
            ),
            idempotency_key=idempotency_key,
        )
        try:
            return await self.repository.add_payment(payment), True
        except DuplicateIdempotencyKeyError:
            if idempotency_key is None:
                raise
            return await self.repository.get_payment_by_key(idempotency_key), False

    async def get_payment(self, payment_id: int) -> Payment:
        return await self.repository.get_payment(payment_id)

    async def list_payments(
        self, email: str | None, status: PaymentStatus | None
    ) -> list[Payment]:
        return await self.repository.list_payments(
            email.lower() if email is not None else None, status
        )

    async def process_webhook(self, payment_id: int, status: PaymentStatus) -> None:
        payment = await self.repository.get_payment(payment_id)
        validate_transition(payment.status, status)
        await self.repository.update_status(payment.id, payment.status, status)
