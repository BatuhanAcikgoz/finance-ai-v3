"""Admin endpoints — LLM key registry, system resource overview, audit log.

All endpoints under /v1/admin/* require an ``X-Admin-Token`` header that matches
``ADMIN_API_TOKEN`` (env). Default dev token is ``dev_admin_token_change_me``.
Comparison uses ``hmac.compare_digest`` to avoid timing leaks.

LLM keys
--------
Admins can register API keys for multiple LLM providers (openai, anthropic,
minimax, deepseek, ollama, custom). The plaintext ``api_key`` is stored but
**never returned** by GET — only the ``masked_key`` (last 4 chars). Live
connectivity is verified via ``/v1/models`` (or ollama's ``/api/tags``).

Security TODO: at-rest encryption of ``admin.llm_keys.api_key`` is not
implemented yet — plaintext in DB. Wire up pgcrypto or app-level AES before
production.

Audit log
---------
Append-only log of admin actions (LLM key create/update/delete, system
view, manual UI-driven entries). Best-effort: log writes never block the
primary action.

Endpoints:
  GET    /v1/admin/llm/keys                   → list keys
  POST   /v1/admin/llm/keys                   → register a key
  POST   /v1/admin/llm/keys/{key_id}/test     → live ping the provider
  PATCH  /v1/admin/llm/keys/{key_id}          → update label/status/model
  DELETE /v1/admin/llm/keys/{key_id}          → remove a key
  POST   /v1/admin/llm/keys/{key_id}/use      → record usage
  GET    /v1/admin/llm/providers              → registry of known providers
  GET    /v1/admin/system                     → host CPU/mem/disk/containers
  GET    /v1/admin/audit-log?limit&since      → tail audit entries
  POST   /v1/admin/audit-log                  → append a UI-side entry
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import platform
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Body, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import db

logger = logging.getLogger(__name__)
router = APIRouter()

# ---- auth -----------------------------------------------------------------

# Default token used when ADMIN_API_TOKEN is unset (dev convenience).
# Production MUST set ADMIN_API_TOKEN to a strong value.
_DEFAULT_ADMIN_TOKEN = "dev_admin_token_change_me"


def _configured_admin_token() -> str:
    """Resolve the configured admin token from env, with a safe default."""
    return os.environ.get("ADMIN_API_TOKEN") or _DEFAULT_ADMIN_TOKEN


def _require_admin(x_admin_token: Optional[str]) -> None:
    """Validate the X-Admin-Token header.

    Uses ``hmac.compare_digest`` to avoid timing leaks. Raises 401 on
    mismatch — the error body matches the standard ``_err`` shape so it
    looks consistent with other 4xx/5xx responses in this codebase.
    """
    expected = _configured_admin_token()
    presented = x_admin_token or ""
    if not presented or not hmac.compare_digest(presented, expected):
        raise HTTPException(
            status_code=401,
            detail="invalid or missing X-Admin-Token header",
        )


# ---- error helper ---------------------------------------------------------

def _err(error: str, detail: str, status_code: int = 503) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": error, "detail": detail})


# ---- provider registry ----------------------------------------------------

# Hardcoded registry. ``custom`` uses api_key as the full URL (no separate
# base_url field), and ``ollama`` hits /api/tags (not /v1/models).
PROVIDER_REGISTRY: list[dict[str, Any]] = [
    {
        "name": "openai",
        "base_url": "https://api.openai.com/v1",
        "requires_key": True,
        "default_model": "gpt-4o-mini",
        "supports_streaming": True,
        "supports_functions": True,
    },
    {
        "name": "anthropic",
        "base_url": "https://api.anthropic.com",
        "requires_key": True,
        "default_model": "claude-3-5-haiku-20241022",
        "supports_streaming": True,
        "supports_functions": False,
    },
    {
        "name": "minimax",
        "base_url": "https://api.MiniMax.chat/v1",
        "requires_key": True,
        "default_model": "MiniMax-M3",
        "supports_streaming": True,
        "supports_functions": True,
    },
    {
        "name": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "requires_key": True,
        "default_model": "deepseek-chat",
        "supports_streaming": True,
        "supports_functions": False,
    },
    {
        "name": "ollama",
        "base_url": "http://localhost:11434",
        "requires_key": False,
        "default_model": "llama3.1",
        "supports_streaming": True,
        "supports_functions": False,
    },
    {
        "name": "custom",
        "base_url": None,  # resolved per-key from api_key
        "requires_key": False,
        "default_model": None,
        "supports_streaming": False,
        "supports_functions": False,
    },
]

_PROVIDER_BY_NAME = {p["name"]: p for p in PROVIDER_REGISTRY}


def _provider_base_url(provider: str, api_key: str) -> str:
    """Return the base URL to ping for ``provider``.

    ``custom`` uses the api_key field as the full URL. ``ollama`` returns
    the registry value directly.
    """
    if provider == "custom":
        return api_key.rstrip("/")
    return _PROVIDER_BY_NAME[provider]["base_url"]


def _model_count_for(provider: str, payload: Any) -> int:
    """Extract ``model_count`` from the response payload of /v1/models.

    openai-compatible: ``{"data": [{"id": "..."}, ...]}``.
    ollama: ``{"models": [{"name": "..."}, ...]}``.
    custom: there is no canonical shape — best effort, length of list
    under ``data``/``models``/``items`` if any.
    """
    if not isinstance(payload, dict):
        return 0
    for key in ("data", "models", "items"):
        v = payload.get(key)
        if isinstance(v, list):
            return len(v)
    return 0


# ---- masking + json helpers ----------------------------------------------

def _mask_key(api_key: str) -> str:
    """Mask an API key for display.

    Uses the spec's contract: show ``sk-...abcd`` style, ending with the
    last 4 characters of the supplied key.
    """
    if not api_key:
        return "****"
    tail = api_key[-4:] if len(api_key) >= 4 else api_key
    return f"sk-...{tail}"


def _to_jsonable(v: Any) -> Any:
    """Convert asyncpg/Decimal/datetime values into JSON-friendly types."""
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, uuid.UUID):
        return str(v)
    return v


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Map an ``admin.llm_keys`` row to the public API response shape.

    The plaintext ``api_key`` is NEVER included — only ``masked_key``.
    """
    return {
        "key_id": str(row["key_id"]),
        "provider": row["provider"],
        "model": row["model"],
        "label": row.get("label"),
        "created_at": _to_jsonable(row.get("created_at")),
        "last_used_at": _to_jsonable(row.get("last_used_at")),
        "status": row.get("status") or "active",
        "masked_key": row.get("masked_key"),
        "cost_usd_total": _to_jsonable(row.get("cost_usd_total")),
        "calls_total": int(row.get("calls_total") or 0),
        "last_error": row.get("last_error"),
    }


# ---- audit helpers --------------------------------------------------------

async def _append_audit(
    *,
    actor: Optional[str],
    action: str,
    target_type: Optional[str],
    target_id: Optional[str],
    summary: Optional[dict] = None,
    ip_addr: Optional[str] = None,
) -> None:
    """Best-effort INSERT into ``admin.audit_log``.

    Never raises — audit failures must not block the primary action.
    """
    try:
        payload = json.dumps(summary or {}, default=str)
        await db.execute(
            """
            INSERT INTO admin.audit_log
                (actor, action, target_type, target_id, summary, ip_addr)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6)
            """,
            actor, action, target_type, target_id, payload, ip_addr,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("admin.audit.append_failed: %s", str(exc))


def _client_ip(request: Request) -> Optional[str]:
    """Best-effort client IP — check X-Forwarded-For first, else the peer."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # First entry is the original client.
        return xff.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return None


# ---- LLM key CRUD ---------------------------------------------------------

class CreateKeyRequest(BaseModel):
    provider: str
    model: str
    api_key: str
    label: Optional[str] = None


class PatchKeyRequest(BaseModel):
    label: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(active|disabled)$")
    model: Optional[str] = None


class UseKeyRequest(BaseModel):
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0


@router.get("/llm/keys")
async def list_llm_keys(
    request: Request,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """List all registered LLM keys (no plaintext api_key returned)."""
    try:
        _require_admin(x_admin_token)
        rows = await db.fetch(
            """
            SELECT key_id, provider, model, label, masked_key, status,
                   cost_usd_total, calls_total, last_used_at, last_error,
                   created_at
            FROM admin.llm_keys
            ORDER BY created_at DESC
            """,
        )
        items = [_row_to_dict(r) for r in rows]
        return {"items": items, "count": len(items)}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("admin.list_llm_keys.error: %s", str(exc))
        return _err("list_llm_keys_failed", str(exc))


@router.post("/llm/keys", status_code=201)
async def create_llm_key(
    request: Request,
    body: CreateKeyRequest,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Register a new LLM key.

    Inserts with status='active' (the spec defers real connectivity testing
    to the explicit ``/test`` endpoint). Audited best-effort.
    """
    try:
        _require_admin(x_admin_token)
        if body.provider not in _PROVIDER_BY_NAME:
            return _err(
                "invalid_provider",
                f"provider {body.provider!r} not in registry",
                status_code=400,
            )
        new_id = uuid.uuid4()
        masked = _mask_key(body.api_key)
        status_msg = await db.execute(
            """
            INSERT INTO admin.llm_keys
                (key_id, provider, model, label, api_key, masked_key, status)
            VALUES ($1, $2, $3, $4, $5, $6, 'active')
            """,
            new_id, body.provider, body.model, body.label,
            body.api_key, masked,
        )
        if not status_msg:
            if not await db.is_available():
                return _err("create_llm_key_failed", "postgres unavailable")
            return _err("create_llm_key_failed", "insert returned no status")

        await _append_audit(
            actor="admin",
            action="llm_key.create",
            target_type="llm_key",
            target_id=str(new_id),
            summary={
                "provider": body.provider,
                "model": body.model,
                "label": body.label,
                "masked_key": masked,
            },
            ip_addr=_client_ip(request),
        )

        return {
            "key_id": str(new_id),
            "status": "testing",  # backwards-compat with spec wording
            "provider": body.provider,
            "model": body.model,
            "label": body.label,
            "masked_key": masked,
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("admin.create_llm_key.error: %s", str(exc))
        return _err("create_llm_key_failed", str(exc))


@router.post("/llm/keys/{key_id}/test")
async def test_llm_key(
    key_id: str,
    request: Request,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Live-ping the provider for ``key_id``.

    Returns ``{key_id, status, latency_ms, model_count, error?}``. Always
    returns a JSON body — never raises on network failure.
    """
    try:
        _require_admin(x_admin_token)
        try:
            key_uuid = uuid.UUID(key_id)
        except ValueError:
            return _err("invalid_key_id", "key_id must be a UUID", status_code=400)

        row = await db.fetchrow(
            """
            SELECT key_id, provider, model, api_key
            FROM admin.llm_keys
            WHERE key_id = $1
            """,
            key_uuid,
        )
        if row is None:
            return _err("key_not_found", f"no key with id {key_id}", status_code=404)

        provider = row["provider"]
        api_key = row["api_key"]
        base = _provider_base_url(provider, api_key)

        # Build ping URL: ollama is special (/api/tags); others hit /v1/models.
        if provider == "ollama":
            ping_url = f"{base.rstrip('/')}/api/tags"
            headers: dict[str, str] = {}
        elif provider == "custom":
            # ``api_key`` is the full URL — skip /models.
            ping_url = base.rstrip("/")
            headers = {}
        else:
            ping_url = f"{base.rstrip('/')}/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}

        started = time.perf_counter()
        status = "invalid"
        model_count = 0
        error: Optional[str] = None
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(ping_url, headers=headers)
                latency_ms = int((time.perf_counter() - started) * 1000)
                if resp.status_code == 200:
                    payload: Any = None
                    try:
                        payload = resp.json()
                    except Exception:
                        payload = None
                    status = "active"
                    model_count = _model_count_for(provider, payload)
                else:
                    status = "invalid"
                    error = f"HTTP {resp.status_code}"
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            status = "invalid"
            error = f"HTTP {exc.response.status_code}"
        except httpx.RequestError as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            status = "invalid"
            error = f"{type(exc).__name__}: {exc}"
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.perf_counter() - started) * 1000)
            status = "invalid"
            error = f"{type(exc).__name__}: {exc}"

        # Persist outcome (best-effort).
        try:
            await db.execute(
                """
                UPDATE admin.llm_keys
                SET status = $2,
                    last_used_at = COALESCE(last_used_at, now()),
                    last_error = $3,
                    updated_at = now()
                WHERE key_id = $1
                """,
                key_uuid, status, error,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("admin.test_llm_key.update_failed: %s", str(exc))

        await _append_audit(
            actor="admin",
            action="llm_key.test",
            target_type="llm_key",
            target_id=key_id,
            summary={
                "provider": provider,
                "status": status,
                "latency_ms": latency_ms,
                "model_count": model_count,
                "error": error,
            },
            ip_addr=_client_ip(request),
        )

        body: dict[str, Any] = {
            "key_id": key_id,
            "status": status,
            "latency_ms": latency_ms,
            "model_count": model_count,
        }
        if error:
            body["error"] = error
        return body
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("admin.test_llm_key.error: %s", str(exc))
        return _err("test_llm_key_failed", str(exc))


@router.patch("/llm/keys/{key_id}")
async def patch_llm_key(
    key_id: str,
    request: Request,
    body: PatchKeyRequest,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Update label / status / model for a registered key."""
    try:
        _require_admin(x_admin_token)
        try:
            key_uuid = uuid.UUID(key_id)
        except ValueError:
            return _err("invalid_key_id", "key_id must be a UUID", status_code=400)

        # Build dynamic SET clause.
        sets: list[str] = []
        args: list[Any] = []
        if body.label is not None:
            args.append(body.label)
            sets.append(f"label = ${len(args)}")
        if body.status is not None:
            args.append(body.status)
            sets.append(f"status = ${len(args)}")
        if body.model is not None:
            args.append(body.model)
            sets.append(f"model = ${len(args)}")

        if not sets:
            return _err(
                "no_fields", "must provide label, status or model",
                status_code=400,
            )
        sets.append("updated_at = now()")
        args.append(key_uuid)
        query = (
            f"UPDATE admin.llm_keys SET {', '.join(sets)} "
            f"WHERE key_id = ${len(args)}"
        )
        status_msg = await db.execute(query, *args)
        if not status_msg:
            if not await db.is_available():
                return _err("patch_llm_key_failed", "postgres unavailable")
            return _err("key_not_found", f"no key with id {key_id}", status_code=404)
        if status_msg.startswith("UPDATE 0"):
            return _err("key_not_found", f"no key with id {key_id}", status_code=404)

        row = await db.fetchrow(
            """
            SELECT key_id, provider, model, label, masked_key, status,
                   cost_usd_total, calls_total, last_used_at, last_error,
                   created_at
            FROM admin.llm_keys
            WHERE key_id = $1
            """,
            key_uuid,
        )
        if row is None:
            return _err("key_not_found", f"no key with id {key_id}", status_code=404)

        await _append_audit(
            actor="admin",
            action="llm_key.update",
            target_type="llm_key",
            target_id=key_id,
            summary=body.model_dump(exclude_none=True),
            ip_addr=_client_ip(request),
        )
        return _row_to_dict(row)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("admin.patch_llm_key.error: %s", str(exc))
        return _err("patch_llm_key_failed", str(exc))


@router.delete("/llm/keys/{key_id}", status_code=204)
async def delete_llm_key(
    key_id: str,
    request: Request,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Delete a registered key. 204 on success, 404 if not found."""
    try:
        _require_admin(x_admin_token)
        try:
            key_uuid = uuid.UUID(key_id)
        except ValueError:
            return _err("invalid_key_id", "key_id must be a UUID", status_code=400)

        status_msg = await db.execute(
            "DELETE FROM admin.llm_keys WHERE key_id = $1",
            key_uuid,
        )
        if not status_msg:
            if not await db.is_available():
                return _err("delete_llm_key_failed", "postgres unavailable")
            return _err("key_not_found", f"no key with id {key_id}", status_code=404)
        if status_msg.startswith("DELETE 0"):
            return _err("key_not_found", f"no key with id {key_id}", status_code=404)

        await _append_audit(
            actor="admin",
            action="llm_key.delete",
            target_type="llm_key",
            target_id=key_id,
            ip_addr=_client_ip(request),
        )
        # 204 with no body.
        return JSONResponse(status_code=204, content=None)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("admin.delete_llm_key.error: %s", str(exc))
        return _err("delete_llm_key_failed", str(exc))


@router.post("/llm/keys/{key_id}/use")
async def record_llm_key_usage(
    key_id: str,
    body: UseKeyRequest,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Increment usage counters for a key (called after each LLM invocation)."""
    try:
        _require_admin(x_admin_token)
        try:
            key_uuid = uuid.UUID(key_id)
        except ValueError:
            return _err("invalid_key_id", "key_id must be a UUID", status_code=400)

        # Append to usage ledger + bump aggregate counters.
        await db.execute(
            """
            INSERT INTO admin.llm_key_usage
                (key_id, cost_usd, prompt_tokens, completion_tokens, status)
            VALUES ($1, $2, $3, $4, 'active')
            """,
            key_uuid, body.cost_usd, body.prompt_tokens, body.completion_tokens,
        )
        status_msg = await db.execute(
            """
            UPDATE admin.llm_keys
            SET calls_total = calls_total + 1,
                cost_usd_total = cost_usd_total + $2,
                last_used_at = now(),
                updated_at = now()
            WHERE key_id = $1
            """,
            key_uuid, body.cost_usd,
        )
        if not status_msg:
            if not await db.is_available():
                return _err("record_usage_failed", "postgres unavailable")
            return _err("key_not_found", f"no key with id {key_id}", status_code=404)
        if status_msg.startswith("UPDATE 0"):
            return _err("key_not_found", f"no key with id {key_id}", status_code=404)

        return {
            "key_id": key_id,
            "recorded": True,
            "cost_usd": body.cost_usd,
            "prompt_tokens": body.prompt_tokens,
            "completion_tokens": body.completion_tokens,
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("admin.record_usage.error: %s", str(exc))
        return _err("record_usage_failed", str(exc))


@router.get("/llm/providers")
async def list_llm_providers(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Static registry of supported LLM providers."""
    try:
        _require_admin(x_admin_token)
        return {"items": PROVIDER_REGISTRY, "count": len(PROVIDER_REGISTRY)}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("admin.list_providers.error: %s", str(exc))
        return _err("list_providers_failed", str(exc))


# ---- system overview ------------------------------------------------------

def _read_proc_meminfo() -> Optional[tuple[int, int]]:
    """Return (used_mb, total_mb) from /proc/meminfo, or None on failure."""
    try:
        info: dict[str, int] = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) != 2:
                    continue
                key, val = parts[0].strip(), parts[1].strip()
                # Values end with " kB".
                if val.endswith(" kB"):
                    try:
                        info[key] = int(val[:-3].strip())
                    except ValueError:
                        pass
        total_kb = info.get("MemTotal")
        avail_kb = info.get("MemAvailable")
        if total_kb is None or avail_kb is None:
            return None
        total_mb = total_kb // 1024
        used_mb = max(0, (total_kb - avail_kb) // 1024)
        return used_mb, total_mb
    except Exception:
        return None


def _read_proc_loadavg() -> Optional[tuple[float, float, float]]:
    """Return (1m, 5m, 15m) load averages from /proc/loadavg, or None."""
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        if len(parts) >= 3:
            return float(parts[0]), float(parts[1]), float(parts[2])
    except Exception:
        return None
    return None


def _read_proc_uptime() -> Optional[float]:
    """Return uptime in seconds from /proc/uptime, or None."""
    try:
        with open("/proc/uptime") as f:
            parts = f.read().split()
        if parts:
            return float(parts[0])
    except Exception:
        return None
    return None


def _cpu_percent_psutil() -> Optional[float]:
    try:
        import psutil  # type: ignore
        return float(psutil.cpu_percent(interval=None))
    except Exception:
        return None


def _mem_psutil() -> Optional[tuple[int, int]]:
    try:
        import psutil  # type: ignore
        vm = psutil.virtual_memory()
        return int(vm.used / (1024 * 1024)), int(vm.total / (1024 * 1024))
    except Exception:
        return None


def _disk_psutil() -> Optional[tuple[float, float]]:
    try:
        import psutil  # type: ignore
        u = psutil.disk_usage("/")
        return round(u.used / (1024 ** 3), 2), round(u.total / (1024 ** 3), 2)
    except Exception:
        return None


def _disk_shutil() -> Optional[tuple[float, float]]:
    try:
        u = shutil.disk_usage("/")
        return round(u.used / (1024 ** 3), 2), round(u.total / (1024 ** 3), 2)
    except Exception:
        return None


async def _list_containers(timeout: float = 3.0) -> list[dict[str, Any]]:
    """Cheap ``docker ps --format json`` enumeration. Empty list on any error."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "ps", "--format", "{{json .}}",
            "--no-trunc",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (FileNotFoundError, OSError, Exception):  # noqa: BLE001
        # docker CLI missing (e.g. running inside an api-gateway container
        # that doesn't bind-mount the docker socket).
        return []
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout,
        )
    except (asyncio.TimeoutError, Exception):  # noqa: BLE001
        try:
            proc.kill()
        except Exception:
            pass
        return []
    if proc.returncode != 0:
        return []
    out: list[dict[str, Any]] = []
    for line in stdout.decode(errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        # ``docker ps --format '{{json .}}'`` returns the template literal
        # with curly braces replaced by JSON object — fields vary by
        # docker version. Common ones: Names, Image, State.
        name = row.get("Names") or row.get("Name") or "?"
        image = row.get("Image") or "?"
        state = row.get("State") or row.get("Status") or "unknown"
        out.append({
            "name": name,
            "image": image,
            "status": state,
            # docker ps --format doesn't expose CPU/mem/net directly. Leave
            # null — callers can cross-reference `docker stats` separately.
            "cpu_pct": None,
            "mem_mb": None,
            "net_rx_bytes": None,
            "net_tx_bytes": None,
        })
    return out


@router.get("/system")
async def system_overview(
    request: Request,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Host-level resource snapshot: CPU, memory, disk, docker containers."""
    try:
        _require_admin(x_admin_token)

        # CPU — psutil first, /proc fallback gives nothing for instant %.
        cpu_pct = _cpu_percent_psutil()

        # Memory — psutil, then /proc/meminfo.
        mem = _mem_psutil() or _read_proc_meminfo()
        mem_used_mb, mem_total_mb = (mem if mem is not None else (None, None))

        # Disk — psutil, then shutil.disk_usage.
        disk = _disk_psutil() or _disk_shutil()
        disk_used_gb, disk_total_gb = (disk if disk is not None else (None, None))

        # Load avg + uptime — /proc only (psutil not needed).
        load = _read_proc_loadavg()
        uptime_s = _read_proc_uptime()

        containers = await _list_containers()

        body = {
            "cpu_pct": cpu_pct,
            "mem_used_mb": mem_used_mb,
            "mem_total_mb": mem_total_mb,
            "disk_used_gb": disk_used_gb,
            "disk_total_gb": disk_total_gb,
            "uptime_s": uptime_s,
            "load_avg_1m_5m_15m": list(load) if load is not None else None,
            "containers": containers,
            "host": platform.node() or "unknown",
            "kernel": " ".join(platform.release().split()[:1]) or "unknown",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        await _append_audit(
            actor="admin",
            action="system.view",
            target_type="system",
            target_id=None,
            summary={"containers_count": len(containers)},
            ip_addr=_client_ip(request),
        )
        return body
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("admin.system_overview.error: %s", str(exc))
        # Per spec: return nulls instead of raising.
        return {
            "cpu_pct": None,
            "mem_used_mb": None,
            "mem_total_mb": None,
            "disk_used_gb": None,
            "disk_total_gb": None,
            "uptime_s": None,
            "load_avg_1m_5m_15m": None,
            "containers": [],
            "host": platform.node() or "unknown",
            "kernel": platform.release() or "unknown",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
        }


# ---- audit log ------------------------------------------------------------

def _parse_since(value: str) -> datetime:
    """Parse ``?since=24h`` style durations. Defaults to 24h on parse failure."""
    now = datetime.now(timezone.utc)
    v = (value or "24h").strip().lower()
    try:
        if v.endswith("h"):
            return now - timedelta(hours=int(v[:-1] or 24))
        if v.endswith("m"):
            return now - timedelta(minutes=int(v[:-1] or 60))
        if v.endswith("d"):
            return now - timedelta(days=int(v[:-1] or 1))
        if v.endswith("s"):
            return now - timedelta(seconds=int(v[:-1] or 3600))
        # Numeric → treat as hours.
        return now - timedelta(hours=int(v))
    except Exception:
        return now - timedelta(hours=24)


class AuditEntry(BaseModel):
    actor: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    summary: Optional[dict] = Field(default=None)
    ip_addr: Optional[str] = None


@router.get("/audit-log")
async def list_audit_log(
    limit: int = Query(100, le=500),
    since: str = Query("24h"),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Tail the ``admin.audit_log`` table, newest first."""
    try:
        _require_admin(x_admin_token)
        since_ts = _parse_since(since)
        rows = await db.fetch(
            """
            SELECT log_id, ts, actor, action, target_type, target_id,
                   summary, ip_addr
            FROM admin.audit_log
            WHERE ts >= $1
            ORDER BY ts DESC
            LIMIT $2
            """,
            since_ts, limit,
        )
        items: list[dict[str, Any]] = []
        for r in rows:
            raw_summary = r.get("summary")
            parsed_summary: Any = raw_summary
            if isinstance(raw_summary, str):
                try:
                    parsed_summary = json.loads(raw_summary)
                except Exception:
                    parsed_summary = raw_summary
            elif isinstance(raw_summary, dict):
                # asyncpg may auto-parse JSONB into dict.
                parsed_summary = raw_summary
            items.append({
                "ts": _to_jsonable(r.get("ts")),
                "actor": r.get("actor"),
                "action": r.get("action"),
                "target_type": r.get("target_type"),
                "target_id": r.get("target_id"),
                "summary": parsed_summary,
                "ip_addr": r.get("ip_addr"),
            })
        return {"items": items, "count": len(items)}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("admin.list_audit_log.error: %s", str(exc))
        return _err("list_audit_log_failed", str(exc))


@router.post("/audit-log", status_code=201)
async def append_audit_log(
    body: AuditEntry,
    request: Request,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Append a UI-driven audit entry (dashboard buttons, manual notes)."""
    try:
        _require_admin(x_admin_token)
        ip = body.ip_addr or _client_ip(request)
        payload = json.dumps(body.summary or {}, default=str)
        status_msg = await db.execute(
            """
            INSERT INTO admin.audit_log
                (actor, action, target_type, target_id, summary, ip_addr)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6)
            """,
            body.actor, body.action, body.target_type, body.target_id,
            payload, ip,
        )
        if not status_msg:
            if not await db.is_available():
                return _err("append_audit_log_failed", "postgres unavailable")
            return _err("append_audit_log_failed", "insert returned no status")

        return {
            "logged": True,
            "actor": body.actor,
            "action": body.action,
            "target_type": body.target_type,
            "target_id": body.target_id,
            "ip_addr": ip,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("admin.append_audit_log.error: %s", str(exc))
        return _err("append_audit_log_failed", str(exc))