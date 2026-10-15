from app.core.enums import PaymentStatus
from app.core.exceptions import (
    DuplicateIdempotencyKeyError,
    InvalidTransitionError,
    PaymentNotFoundError,
    TariffNotFoundError,
)
from app.models.billing import Payment, Tariff
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class BillingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def has_tariffs(self) -> bool:
        result = await self.db.scalar(select(Tariff.id).limit(1))
        return result is not None

    async def add_tariffs(self, tariffs: list[Tariff]) -> None:
        self.db.add_all(tariffs)
        await self.db.commit()

    async def list_tariffs(self) -> list[Tariff]:
        return list(await self.db.scalars(select(Tariff).order_by(Tariff.id)))

    async def get_tariff(self, tariff_id: int) -> Tariff:
        tariff = await self.db.get(Tariff, tariff_id)
        if tariff is None:
            raise TariffNotFoundError("Tariff not found")
        return tariff

    async def get_payment(self, payment_id: int) -> Payment:
        payment = await self.db.get(Payment, payment_id)
        if payment is None:
            raise PaymentNotFoundError("Payment not found")
        return payment

    async def get_payment_by_key(self, key: str) -> Payment:
        payment = await self.db.scalar(
            select(Payment).where(Payment.idempotency_key == key)
        )
        if payment is None:
            raise PaymentNotFoundError("Payment not found")
        return payment

    async def add_payment(self, payment: Payment) -> Payment:
        self.db.add(payment)
        try:
            await self.db.commit()
        except IntegrityError as error:
            await self.db.rollback()
            if payment.idempotency_key is not None:
                existing = await self.db.scalar(
                    select(Payment.id).where(
                        Payment.idempotency_key == payment.idempotency_key
                    )
                )
                if existing is not None:
                    raise DuplicateIdempotencyKeyError() from error
            raise
        await self.db.refresh(payment)
        return payment

    async def list_payments(
        self, email: str | None, status: PaymentStatus | None
    ) -> list[Payment]:
        query = select(Payment).order_by(Payment.id.desc())
        if email is not None:
            query = query.where(Payment.email == email)
        if status is not None:
            query = query.where(Payment.status == status)
        return list(await self.db.scalars(query))

    async def update_status(
        self, payment_id: int, current: PaymentStatus, target: PaymentStatus
    ) -> None:
        changed_id = await self.db.scalar(
            update(Payment)
            .where(Payment.id == payment_id, Payment.status == current)
            .values(status=target)
            .returning(Payment.id)
        )
        if changed_id is None:
            await self.db.rollback()
            raise InvalidTransitionError("Payment status changed concurrently")
        await self.db.commit()
