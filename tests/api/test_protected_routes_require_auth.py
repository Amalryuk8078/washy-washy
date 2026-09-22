"""HTTP-level tests confirming every Phase 4 endpoint actually requires
authentication. Runs without a database: ``get_current_user`` rejects a
missing/malformed token before any route handler — and therefore before
any DB access — runs.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/users/me"),
        ("GET", "/api/v1/customers/me"),
        ("POST", "/api/v1/customers/me"),
        ("GET", "/api/v1/addresses"),
        ("POST", "/api/v1/addresses"),
        ("GET", "/api/v1/service-areas"),
        ("POST", "/api/v1/service-areas"),
    ],
)
async def test_endpoint_rejects_missing_token(client: AsyncClient, method: str, path: str) -> None:
    response = await client.request(method, path, json={})
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["code"] == "AUTH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_endpoint_rejects_malformed_bearer_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_TOKEN_INVALID"
