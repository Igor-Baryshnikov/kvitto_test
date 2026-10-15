from datetime import datetime, timezone

from app.core.database import Base
from app.core.enums import PaymentMethod, PaymentStatus
from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Tariff(Base):
    __tablename__ = "tariffs"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), unique=True)
    price: Mapped[int] = mapped_column(Integer)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    tariff_id: Mapped[int] = mapped_column(ForeignKey("tariffs.id"))
    email: Mapped[str] = mapped_column(String(320))
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, native_enum=False, create_constraint=True)
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False, create_constraint=True),
        default=PaymentStatus.pending,
    )
    amount: Mapped[int] = mapped_column(Integer)
    discount: Mapped[int] = mapped_column(Integer, default=0)
    installment_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule: Mapped[list[int] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
