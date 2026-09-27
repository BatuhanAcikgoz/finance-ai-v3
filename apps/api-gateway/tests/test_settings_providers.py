"""Tests for the LLM provider registry + settings validation."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

import main as main_module
import redis_cache
from routes import settings as settings_module


# ---------------------------------------------------------------------------
# Sync unit tests — exercise the in-process provider registry without any
# Redis / network round-trips.
# ---------------------------------------------------------------------------


def test_minimax_is_first_provider_openai_format():
    """MiniMax is OpenAI-compatible on https://api.minimax.io/v1."""
    p = settings_module.provider_by_id("minimax")
    assert p is not None, "minimax must be in the registry"
    assert p["api_format"] == "openai"
    assert p["base_url"].startswith("https://api.minimax.io/")
    assert "minimax-m3" in p["models"]
    assert p["default_model"] == "minimax-m3"


def test_default_settings_use_MiniMax():
    """Out-of-the-box the platform defaults to MiniMax-M3 in OpenAI format."""
    s = settings_module.DEFAULT_SETTINGS
    assert s["llm"]["provider"] == "minimax"
    assert s["llm"]["model"] == "minimax-m3"
    assert s["llm"]["api_format"] == "openai"


def test_provider_by_id_returns_none_for_unknown():
    assert settings_module.provider_by_id("does-not-exist") is None


def test_every_provider_has_required_fields():
    """Guard against partial provider entries leaking through."""
    required = {"id", "label", "api_format", "base_url",
                "default_model", "models", "needs_key", "notes"}
    for p in settings_module.PROVIDERS:
        assert required.issubset(p.keys()), f"{p['id']} missing fields: {required - p.keys()}"
        assert isinstance(p["models"], list) and p["models"], f"{p['id']}: models must be non-empty list"
        assert p["default_model"] in p["models"], (
            f"{p['id']}: default_model {p['default_model']!r} not in models {p['models']!r}"
        )


# ---------------------------------------------------------------------------
# Async tests over HTTP — exercise the GET/PATCH /v1/settings endpoint with
# Redis monkey-patched to an in-memory dict.
# ---------------------------------------------------------------------------


class _FakeRedis:
    """Just enough of the redis_cache API surface for settings to work."""
    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, *args, **kwargs):
        self._store[key] = value
        return True


@pytest.fixture
def fake_redis(monkeypatch):
    """Monkeypatch redis_cache.get_json / set_json with in-memory equivalents."""
    fake = _FakeRedis()

    async def _fake_get_json(key):
        v = await fake.get(key)
        if v is None:
            return None
        import json as _json
        return _json.loads(v)

    async def _fake_set_json(key, value, ttl_seconds=60):
        import json as _json
        await fake.set(key, _json.dumps(value))
        return True

    monkeypatch.setattr(redis_cache, "get_json", _fake_get_json)
    monkeypatch.setattr(redis_cache, "set_json", _fake_set_json)
    return fake


@pytest.mark.asyncio
async def test_get_settings_includes_providers(fake_redis):
    async with AsyncClient(transport=ASGITransport(app=main_module.app), base_url="http://test", follow_redirects=True) as ac:
        r = await ac.get("/v1/settings")
    assert r.status_code == 200
    body = r.json()
    assert "providers" in body
    ids = {p["id"] for p in body["providers"]}
    assert {"minimax", "openai", "anthropic", "gemini", "ollama"}.issubset(ids)
    assert body["llm"]["provider"] == "minimax"
    assert body["llm"]["model"] == "minimax-m3"
    assert body["llm"]["api_format"] == "openai"


@pytest.mark.asyncio
async def test_patch_provider_swaps_to_default_model(fake_redis):
    """Switching only the provider must auto-fill its default model —
    prevents ending up with provider=anthropic + model=gpt-4o."""
    async with AsyncClient(transport=ASGITransport(app=main_module.app), base_url="http://test", follow_redirects=True) as ac:
        r = await ac.patch("/v1/settings", json={"llm": {"provider": "anthropic"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["llm"]["provider"] == "anthropic"
    assert body["llm"]["model"] == "claude-3-7-sonnet"
    assert body["llm"]["api_format"] == "anthropic"


@pytest.mark.asyncio
async def test_patch_unknown_provider_returns_400(fake_redis):
    async with AsyncClient(transport=ASGITransport(app=main_module.app), base_url="http://test", follow_redirects=True) as ac:
        r = await ac.patch("/v1/settings", json={"llm": {"provider": "made-up-llm"}})
    assert r.status_code == 400, r.text
    body = r.json()
    assert body["error"] == "unknown_provider"
    assert "minimax" in body["detail"]


@pytest.mark.asyncio
async def test_patch_model_only_does_not_clobber_provider(fake_redis):
    """Setting only the model must NOT override the active provider."""
    async with AsyncClient(transport=ASGITransport(app=main_module.app), base_url="http://test", follow_redirects=True) as ac:
        r = await ac.patch("/v1/settings", json={"llm": {"model": "minimax-m2"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["llm"]["provider"] == "minimax"
    assert body["llm"]["model"] == "minimax-m2"


@pytest.mark.asyncio
async def test_providers_endpoint_only(fake_redis):
    async with AsyncClient(transport=ASGITransport(app=main_module.app), base_url="http://test", follow_redirects=True) as ac:
        r = await ac.get("/v1/settings/providers")
    assert r.status_code == 200
    body = r.json()
    assert "providers" in body
    # The smaller endpoint intentionally doesn't carry the rest of settings.
    assert "llm" not in body
    assert "risk" not in body
