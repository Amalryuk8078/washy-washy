from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from core.database.session import get_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
