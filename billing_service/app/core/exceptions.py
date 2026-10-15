class PaymentNotFoundError(Exception):
    pass


class TariffNotFoundError(Exception):
    pass


class InvalidTransitionError(Exception):
    pass


class UnknownPromoCodeError(Exception):
    pass


class DuplicateIdempotencyKeyError(Exception):
    pass


class InvalidInstallmentError(Exception):
    pass


class InvalidAmountError(Exception):
    pass
