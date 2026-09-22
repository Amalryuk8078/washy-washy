import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"


@pytest.mark.asyncio
async def test_health_live(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready_shape(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert "checks" in body["data"]
    assert "postgres" in body["data"]["checks"]


@pytest.mark.asyncio
async def test_request_id_header_echoed(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"


@pytest.mark.asyncio
async def test_request_id_header_generated(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.headers["X-Request-ID"]
