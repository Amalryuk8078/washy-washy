"""HTTP-level tests for the Phase 2 auth routes, via the ASGI transport
client (tests/conftest.py). Limited to paths that don't touch the
database — request validation, and refresh-token decoding (which
happens before any DB access) — so this file runs without PostgreSQL.
End-to-end register/login/refresh flows are covered by
tests/integration/test_auth.py.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_rejects_short_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "short", "first_name": "A"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_register_rejects_malformed_email(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "longenough1", "first_name": "A"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_rejects_missing_password(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/login", json={"email": "a@example.com"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_refresh_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["code"] == "AUTH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_refresh_rejects_missing_body_field(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh", json={})
    assert response.status_code == 422
