"""Smoke tests for /health — must work whether infra is up or down."""
import pytest
from httpx import ASGITransport, AsyncClient

import db
import redis_cache
import main as main_module


@pytest.fixture
async def client():
    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_basic(client):
    r = await client.get("/health/")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["service"] == "finance-ai-v3"


async def test_health_ready_degrades_when_infra_down(monkeypatch, client):
    """If db/redis/qdrant all return False, /ready reports degraded but 200."""
    async def _db_false():
        return False
    async def _redis_false():
        return False
    async def _qdrant_false():
        return False

    monkeypatch.setattr(db, "is_available", _db_false)
    monkeypatch.setattr(redis_cache, "is_available", _redis_false)
    monkeypatch.setattr("routes.health._qdrant_ping", _qdrant_false)

    r = await client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["db"] is False
    assert body["redis"] is False
    assert body["qdrant"] is False
    assert "version" in body


async def test_health_live(client):
    r = await client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"