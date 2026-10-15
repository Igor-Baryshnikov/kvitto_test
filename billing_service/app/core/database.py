import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

env_path = Path(__file__).parents[3] / ".env"

load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./payments.db")

engine = create_async_engine(DATABASE_URL, echo=False)


class Base(DeclarativeBase):
    pass


AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)
