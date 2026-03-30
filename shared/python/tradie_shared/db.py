from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .settings import AppSettings


def build_engine(settings: AppSettings):
    return create_async_engine(settings.database_url, pool_pre_ping=True, future=True)


def build_session_factory(settings: AppSettings) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(build_engine(settings), expire_on_commit=False)


async def session_dependency(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session
