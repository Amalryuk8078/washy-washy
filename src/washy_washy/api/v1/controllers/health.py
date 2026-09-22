"""Request-level orchestration for health endpoints.

Thin on purpose: it asks the database "are you reachable?" and shapes the
result into the common response envelope. Once Redis/Celery are introduced
(Phase 11), their checks are added here, not in the route.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_liveness() -> dict:
    return {"status": "ok"}


async def get_readiness(db_session: AsyncSession) -> dict:
    checks = {"postgres": await _check_postgres(db_session)}
    ready = all(checks.values())
    return {"status": "ok" if ready else "degraded", "checks": checks}


async def _check_postgres(db_session: AsyncSession) -> bool:
    try:
        await db_session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
