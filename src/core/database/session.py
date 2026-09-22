from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.database.engine import get_engine


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
