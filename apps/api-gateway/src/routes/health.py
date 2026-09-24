"""Health endpoints: basic ping + per-dependency status.

Always returns 200 unless the process itself is broken. Individual dependency
states (db/redis/qdrant) are reported in the body so an orchestrator can
distinguish "alive but degraded" from "fully ready".
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter

import db
import redis_cache
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


async def _qdrant_ping() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{settings.qdrant_url}/health")
        return r.status_code == 200
    except Exception as exc:
        logger.warning("health.qdrant.ping_failed: %s", str(exc))
        return False


@router.get("/")
async def health_check() -> dict:
    """Basic health — always returns 200."""
    return {"status": "healthy", "service": "finance-ai-v3"}


@router.get("/ready")
async def readiness_check() -> dict:
    """Detailed readiness: pings every dependency.

    Returns 200 even when degraded (per spec: log warning, don't crash).
    Orchestrator should poll ``status`` field for ``"degraded"`` vs ``"ready"``.
    """
    db_ok = await db.is_available()
    redis_ok = await redis_cache.is_available()
    qdrant_ok = await _qdrant_ping()

    all_ok = db_ok and redis_ok and qdrant_ok
    return {
        "status": "ready" if all_ok else "degraded",
        "version": settings.app_version,
        "db": db_ok,
        "redis": redis_ok,
        "qdrant": qdrant_ok,
    }


@router.get("/live")
async def liveness_check() -> dict:
    """Liveness — the process is up."""
    return {"status": "alive"}