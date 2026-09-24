"""Settings endpoint tests — uses monkeypatched Redis cache."""

import pytest
from httpx import ASGITransport, AsyncClient

import main as main_module
import routes.settings as settings_module


@pytest.fixture
async def client():
    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_get_settings_returns_defaults(client, monkeypatch):
    """GET /v1/settings should return the documented default shape when Redis
    is empty / unreachable."""
    async def fake_get_json(key):
        return None
    async def fake_set_json(key, value, ttl_seconds=60):
        return True

    monkeypatch.setattr(settings_module.redis_cache, "get_json", fake_get_json)
    monkeypatch.setattr(settings_module.redis_cache, "set_json", fake_set_json)

    r = await client.get("/v1/settings/")
    assert r.status_code == 200
    body = r.json()
    assert body["user"] == "dev"
    assert body["notify"]["email"] is True
    assert body["risk"]["max_position_pct"] == 0.10
    assert body["llm"]["provider"] == "openai"
    assert body["llm"]["model"] == "gpt-4o"
    assert body["llm"]["monthly_budget_usd"] == 500
    assert "bloomberght" in body["sources"]["news"]


async def test_patch_settings_merges_and_persists(client, monkeypatch):
    """PATCH should deep-merge, persist to Redis, and echo back the merged state."""
    stored: dict = {}

    async def fake_get_json(key):
        return dict(stored) if stored else None
    async def fake_set_json(key, value, ttl_seconds=60):
        stored.clear()
        stored.update(value)
        return True

    monkeypatch.setattr(settings_module.redis_cache, "get_json", fake_get_json)
    monkeypatch.setattr(settings_module.redis_cache, "set_json", fake_set_json)

    r = await client.patch(
        "/v1/settings/",
        json={
            "risk": {"max_position_pct": 0.07},
            "llm": {"model": "gpt-4o-mini", "monthly_budget_usd": 250},
        },
    )
    assert r.status_code == 200
    body = r.json()
    # Updated fields
    assert body["risk"]["max_position_pct"] == 0.07
    assert body["llm"]["model"] == "gpt-4o-mini"
    assert body["llm"]["monthly_budget_usd"] == 250
    # Untouched fields preserved from defaults
    assert body["risk"]["max_sector_pct"] == 0.30
    assert body["llm"]["provider"] == "openai"
    assert body["notify"]["email"] is True
