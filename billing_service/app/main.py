from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.api.routers.billing import router
from app.core.database import AsyncSessionLocal, engine
from app.core.exceptions import (
    InvalidInstallmentError,
    InvalidTransitionError,
    PaymentNotFoundError,
    TariffNotFoundError,
    UnknownPromoCodeError,
)
from app.repositories.billing import BillingRepository
from app.services.billing import BillingService
from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        async with AsyncSessionLocal() as session:
            await BillingService(BillingRepository(session)).seed_tariffs()
        yield
    finally:
        await engine.dispose()


app = FastAPI(title="Kvitto Billing API", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(PaymentNotFoundError)
@app.exception_handler(TariffNotFoundError)
async def not_found_handler(
    request: Request, error: PaymentNotFoundError | TariffNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.exception_handler(InvalidTransitionError)
async def transition_handler(
    request: Request, error: InvalidTransitionError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"error": "invalid_transition"})


@app.exception_handler(UnknownPromoCodeError)
@app.exception_handler(InvalidInstallmentError)
async def validation_handler(
    request: Request, error: UnknownPromoCodeError | InvalidInstallmentError
) -> JSONResponse:
    field = (
        "promo_code"
        if isinstance(error, UnknownPromoCodeError)
        else "installment_months"
    )
    validation_error = RequestValidationError(
        [
            {
                "type": "value_error",
                "loc": ("body", field),
                "msg": str(error),
                "input": None,
            }
        ]
    )
    return await request_validation_exception_handler(request, validation_error)
