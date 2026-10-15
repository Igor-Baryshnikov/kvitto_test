from collections.abc import AsyncIterator

import pytest
from app.core.database import Base
from app.core.dependencies import get_async_db
from app.main import app
from app.repositories.billing import BillingRepository
from app.services.billing import BillingService
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as database_session:
        yield database_session


@pytest.fixture
async def service(session: AsyncSession) -> BillingService:
    billing_service = BillingService(BillingRepository(session))
    await billing_service.seed_tariffs()
    return billing_service


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
    service: BillingService,
) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as database_session:
            yield database_session

    app.dependency_overrides[get_async_db] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test/"
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
