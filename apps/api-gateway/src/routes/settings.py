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
        "provider": "minimax",
        "model": "minimax-m3",
        "api_format": "openai",
        "monthly_budget_usd": 500,
    },
}

# Provider registry — every dashboard <select> is populated from this list.
# `api_format` describes how requests are shaped:
#   * "openai" — POST {base}/chat/completions with OpenAI ChatCompletion body.
#     MiniMax is fully OpenAI-compatible on https://api.MiniMax.chat/v1 so
#     it's listed here. Anthropic/Gemini use their native shapes when we
#     wire those providers in.
# `base_url` is consulted by the dispatcher; missing here means the route
# relies on the default OpenAI-compatible adapter.
# `models` is what shows up in the settings-model <select>; each provider's
# first entry doubles as the default when the user picks a new provider.
PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "minimax",
        "label": "MiniMax",
        "api_format": "openai",
        "base_url": "https://api.MiniMax.chat/v1",
        "default_model": "minimax-m3",
        "models": [
            "minimax-m3",
            "minimax-m2",
            "minimax-vl-01",
        ],
        "needs_key": True,
        "notes": "Açık kaynak / Open-source. OpenAI ChatCompletion formatını kullanır. Ücretsiz plan başlangıç için yeterli.",
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "api_format": "openai",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4.1",
            "gpt-4.1-mini",
            "o4-mini",
        ],
        "needs_key": True,
        "notes": "OpenAI ChatCompletion API; fiyatlandırma $/$+ oranı.",
    },
    {
        "id": "anthropic",
        "label": "Anthropic",
        "api_format": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-3-7-sonnet",
        "models": [
            "claude-3-7-sonnet",
            "claude-3-5-haiku",
            "claude-opus-4",
        ],
        "needs_key": True,
        "notes": "Anthropic Messages API'si.",
    },
    {
        "id": "gemini",
        "label": "Google Gemini",
        "api_format": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_model": "gemini-1.5-pro",
        "models": [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.0-flash",
        ],
        "needs_key": True,
        "notes": "Google Generative Language API.",
    },
    {
        "id": "mistral",
        "label": "Mistral",
        "api_format": "openai",
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-large-latest",
        "models": [
            "mistral-large-latest",
            "mistral-small-latest",
            "codestral-latest",
        ],
        "needs_key": True,
        "notes": "OpenAI-uyumlu uç nokta.",
    },
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "api_format": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "models": [
            "deepseek-chat",
            "deepseek-reasoner",
        ],
        "needs_key": True,
        "notes": "OpenAI-uyumlu uç nokta.",
    },
    {
        "id": "ollama",
        "label": "Ollama (local)",
        "api_format": "openai",
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.2",
        "models": [
            "llama3.2",
            "qwen2.5",
            "mistral",
            "gemma2",
        ],
        "needs_key": False,
        "notes": "Yerel inference. API anahtarı gerekmez.",
    },
]


def provider_by_id(pid: str) -> dict[str, Any] | None:
    for p in PROVIDERS:
        if p["id"] == pid:
            return p
    return None


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
    """Return the current settings object with defaults filled in.

    The response also carries ``providers`` — the canonical list used by
    the dashboard to populate the LLM-provider <select>. Keeping this in
    one place means the UI cannot drift from the backend's allowlist.
    """
    try:
        state = await _load()
        # Fill in model/api_format if the saved state lacks them but the
        # provider exists in the registry — keeps legacy Redis payloads
        # upgrade-safe.
        if isinstance(state.get("llm"), dict):
            p = provider_by_id(state["llm"].get("provider", ""))
            if p:
                state["llm"].setdefault("api_format", p["api_format"])
                state["llm"].setdefault("model", p["default_model"])
        # Recompute effective api_format in case the saved provider was
        # changed manually outside the registry (e.g. legacy "minimax"
        # alias).
        if state["llm"].get("provider") and provider_by_id(state["llm"]["provider"]) is None:
            state["llm"]["api_format"] = state["llm"].get("api_format", "openai")
        return {
            **state,
            "providers": PROVIDERS,
        }
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("settings.get.error: %s", str(exc))
        return _err("get_settings_failed", str(exc))


@router.get("/providers")
async def list_providers():
    """Just the provider registry — convenient for the LLM-keys page and
    other UI surfaces that don't need the full settings blob."""
    try:
        return {"providers": PROVIDERS}
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("settings.providers.error: %s", str(exc))
        return _err("list_providers_failed", str(exc))


@router.patch("/")
async def patch_settings(patch: dict = Body(...)):
    """Merge ``patch`` into the stored settings and persist.

    Body shape mirrors the GET response: any subset of the top-level keys
    (``notify``, ``sources``, ``risk``, ``llm``) is accepted. Values must be
    dicts (for nested sections) — primitive top-level patches are ignored.
    For ``llm.provider``, the value is validated against ``PROVIDERS`` and
    ``llm.model`` is backfilled to that provider's default when missing.
    """
    try:
        # Guard: invalid provider → 400, never silently coerce.
        if isinstance(patch, dict) and isinstance(patch.get("llm"), dict):
            prov = patch["llm"].get("provider")
            if prov and provider_by_id(prov) is None:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "unknown_provider",
                        "detail": f"provider {prov!r} is not registered. "
                                  f"Choose one of: {[p['id'] for p in PROVIDERS]}",
                    },
                )
            if prov:
                meta = provider_by_id(prov)
                if meta is None:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "unknown_provider", "detail": prov},
                    )
                # When the user only switches provider, take its default model
                # so we never end up with e.g. provider=minimax + model=gpt-4o.
                patch_llm = dict(patch["llm"])
                if "model" not in patch_llm:
                    patch_llm["model"] = meta["default_model"]
                # api_format mirrors the provider's unless explicitly set.
                if "api_format" not in patch_llm:
                    patch_llm["api_format"] = meta["api_format"]
                patch = {**patch, "llm": patch_llm}

        current = await _load()
        merged = _deep_merge(current, patch)
        await _save(merged)
        return merged
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("settings.patch.error: %s", str(exc))
        return _err("patch_settings_failed", str(exc))
