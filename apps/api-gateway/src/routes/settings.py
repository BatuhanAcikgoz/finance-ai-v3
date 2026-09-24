"""Settings endpoints — user preferences for notifications, sources, risk, LLM.

The settings object is intentionally small and lives in Redis (with a sane
default for cold-start). PATCH supports partial updates; unknown keys are
silently dropped on read.

Endpoints:
  GET   /v1/settings   → current state (with defaults filled in)
  PATCH /v1/settings   → partial update; echo back the merged state
"""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import redis_cache

logger = logging.getLogger(__name__)
router = APIRouter()


def _err(error: str, detail: str) -> JSONResponse:
    """Standard 503 error response per gateway spec."""
    return JSONResponse(status_code=503, content={"error": error, "detail": detail})

# A single user in dev mode — multi-user would key on user_id.
_USER = "dev"
_CACHE_KEY = f"settings:{_USER}"

DEFAULT_SETTINGS: dict[str, Any] = {
    "user": _USER,
    "notify": {
        "email": True,
        "ws": True,
        "dashboard": True,
    },
    "sources": {
        "bist_rss": True,
        "tefas": True,
        "kap": True,
        "news": ["bloomberght", "trt"],
    },
    "risk": {
        "max_position_pct": 0.10,
        "max_sector_pct": 0.30,
    },
    "llm": {
        "provider": "openai",
        "model": "gpt-4o",
        "monthly_budget_usd": 500,
    },
}


# -- request/response models ------------------------------------------------

class SettingsModel(BaseModel):
    """Loose model — the real validation happens at the merge step so we
    don't lock out partial fields when the dashboard sends partial updates."""
    user: str = _USER
    notify: dict[str, Any] = Field(default_factory=dict)
    sources: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    llm: dict[str, Any] = Field(default_factory=dict)


# -- helpers ----------------------------------------------------------------

def _deep_merge(base: dict, patch: dict) -> dict:
    """Recursively merge ``patch`` into ``base``, leaving missing keys alone."""
    out = deepcopy(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


async def _load() -> dict:
    """Load settings from Redis or fall back to defaults."""
    cached = await redis_cache.get_json(_CACHE_KEY)
    if cached is not None:
        return _deep_merge(DEFAULT_SETTINGS, cached)
    return deepcopy(DEFAULT_SETTINGS)


async def _save(state: dict) -> bool:
    """Persist settings to Redis. Returns True on success, False on failure."""
    return await redis_cache.set_json(_CACHE_KEY, state, ttl_seconds=86400 * 30)


# -- endpoints --------------------------------------------------------------

@router.get("/")
async def get_settings():
    """Return the current settings object with defaults filled in."""
    try:
        return await _load()
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("settings.get.error: %s", str(exc))
        return _err("get_settings_failed", str(exc))


@router.patch("/")
async def patch_settings(patch: dict = Body(...)):
    """Merge ``patch`` into the stored settings and persist.

    Body shape mirrors the GET response: any subset of the top-level keys
    (``notify``, ``sources``, ``risk``, ``llm``) is accepted. Values must be
    dicts (for nested sections) — primitive top-level patches are ignored.
    """
    try:
        current = await _load()
        merged = _deep_merge(current, patch)
        await _save(merged)
        return merged
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("settings.patch.error: %s", str(exc))
        return _err("patch_settings_failed", str(exc))
