from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from core.config import get_core_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_core_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
    )
