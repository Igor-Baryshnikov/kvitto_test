from collections.abc import AsyncIterator

from app.core.database import AsyncSessionLocal
from app.repositories.billing import BillingRepository
from app.services.billing import BillingService
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession


async def get_async_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as db:
        yield db


def get_billing_repo(db: AsyncSession = Depends(get_async_db)) -> BillingRepository:
    return BillingRepository(db)


def get_billing_service(
    billing_repo: BillingRepository = Depends(get_billing_repo),
) -> BillingService:
    return BillingService(billing_repo)
