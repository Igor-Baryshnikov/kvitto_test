from enum import StrEnum


class PaymentMethod(StrEnum):
    card = "card"
    sbp = "sbp"
    installment = "installment"


class PaymentStatus(StrEnum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    refunded = "refunded"
