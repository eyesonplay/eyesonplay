"""SQLAlchemy engine/session setup."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import JSON, BigInteger, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# JSONB / BIGSERIAL on Postgres; portable fallbacks keep tests runnable on SQLite.
JsonType = JSONB().with_variant(JSON(), "sqlite")
BigIntPk = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    pass


def create_engine(url: str) -> AsyncEngine:
    kwargs = {} if url.startswith("sqlite") else {"pool_size": 10, "max_overflow": 10, "pool_pre_ping": True}
    return create_async_engine(url, **kwargs)


def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_scope(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session
