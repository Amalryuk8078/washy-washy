import os
from pathlib import Path

# CoreSettings reads `.env` directly (pydantic-settings' env_file), but an
# OS environment variable always outranks it — so setting these
# unconditionally would shadow a real, already-correct `.env` (e.g. a
# locally customized POSTGRES_PASSWORD) with these stale placeholders,
# silently breaking every DB-dependent test's connection. Only fall back
# to them when there's no `.env` to read at all (a bare checkout/CI).
if not (Path(__file__).resolve().parent.parent / ".env").exists():
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+asyncpg://washy:change_me@localhost:5432/washy_washy"
    )
    os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from httpx import ASGITransport, AsyncClient

from washy_washy.main import app


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
