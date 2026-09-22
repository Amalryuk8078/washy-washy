"""Integration check for the async engine/session against a real
PostgreSQL instance (``docker compose up postgres`` or a local install —
see ``.env``/``.env.example`` for the connection settings).

Skips instead of failing when PostgreSQL isn't reachable so the default
``pytest`` run stays self-contained; Washy Washy is PostgreSQL-first and
this intentionally does not fall back to SQLite.
"""

import pytest
from sqlalchemy import text

from core.database.session import get_session_factory


@pytest.mark.asyncio
async def test_select_1_against_real_postgres() -> None:
    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            result = await session.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL is not reachable: {exc}")
    else:
        assert result.scalar_one() == 1
