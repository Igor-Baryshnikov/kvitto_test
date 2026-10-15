from datetime import datetime
from typing import Self

from app.core.enums import PaymentMethod, PaymentStatus
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class PaymentCreate(BaseModel):
    tariff_id: int = Field(gt=0, strict=True)
    email: EmailStr
    method: PaymentMethod
    installment_months: int | None = Field(default=None, strict=True)
    promo_code: str | None = None

    @model_validator(mode="after")
    def validate_installments(self) -> Self:
        if self.method == PaymentMethod.installment:
            if self.installment_months not in {3, 6, 12}:
                raise ValueError("installment_months must be 3, 6 or 12")
        elif self.installment_months is not None:
            raise ValueError("installment_months is only allowed for installment")
        return self


class TariffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    price: int


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: PaymentStatus
    tariff_id: int
    amount: int
    discount: int
    method: PaymentMethod
    installment_months: int | None
    schedule: list[int] | None
    email: str
    created_at: datetime


class BankWebhook(BaseModel):
    payment_id: int = Field(gt=0, strict=True)
    status: PaymentStatus
