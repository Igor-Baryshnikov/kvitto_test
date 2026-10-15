from typing import Annotated

from app.core.dependencies import get_billing_service
from app.core.enums import PaymentStatus
from app.schemas.billing import (
    BankWebhook,
    PaymentCreate,
    PaymentResponse,
    TariffResponse,
)
from app.services.billing import BillingService
from fastapi import APIRouter, Depends, Header, Response

router = APIRouter(tags=["billing"])


@router.get("/tariffs", response_model=list[TariffResponse])
async def list_tariffs(
    billing_service: BillingService = Depends(get_billing_service),
) -> list[TariffResponse]:
    tariffs = await billing_service.list_tariffs()
    return [TariffResponse.model_validate(tariff) for tariff in tariffs]


@router.post("/payments", response_model=PaymentResponse, status_code=201)
async def create_payment(
    body: PaymentCreate,
    response: Response,
    billing_service: BillingService = Depends(get_billing_service),
    idempotency_key: Annotated[str | None, Header(max_length=255)] = None,
) -> PaymentResponse:
    payment, created = await billing_service.create_payment(
        body.tariff_id,
        str(body.email),
        body.method,
        body.installment_months,
        body.promo_code,
        idempotency_key,
    )
    response.status_code = 201 if created else 200
    return PaymentResponse.model_validate(payment)


@router.get("/payments", response_model=list[PaymentResponse])
async def list_payments(
    billing_service: BillingService = Depends(get_billing_service),
    email: str | None = None,
    status: PaymentStatus | None = None,
) -> list[PaymentResponse]:
    payments = await billing_service.list_payments(email, status)
    return [PaymentResponse.model_validate(payment) for payment in payments]


@router.get("/payments/{id}", response_model=PaymentResponse)
async def get_payment(
    id: int, billing_service: BillingService = Depends(get_billing_service)
) -> PaymentResponse:
    payment = await billing_service.get_payment(id)
    return PaymentResponse.model_validate(payment)


@router.post("/webhooks/bank")
async def bank_webhook(
    body: BankWebhook, billing_service: BillingService = Depends(get_billing_service)
) -> dict[str, str]:
    await billing_service.process_webhook(body.payment_id, body.status)
    return {"result": "ok"}
