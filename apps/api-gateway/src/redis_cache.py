"""Thin ``redis.asyncio`` wrapper with JSON helpers + TTL.

Import-safe: ``get_client()`` returns ``None`` if Redis is unreachable.
``get_json`` / ``set_json`` degrade to defaults rather than raise, so endpoints
stay responsive when Redis is down (cache is a performance optimisation,
not a source of truth).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from config import settings

logger = logging.getLogger(__name__)

_client: Optional[aioredis.Redis] = None
_available: Optional[bool] = None


def get_client() -> Optional[aioredis.Redis]:
    """Lazily create and return the redis client (synchronous, no await).

    Redis-py clients are lazy and won't connect until first command — so this
    is safe to call at import time and cheap to call repeatedly.
    """
    global _client
    if _client is not None:
        return _client
    try:
        _client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("redis.client.create_failed: %s", str(exc))
        _client = None
    return _client


async def close_client() -> None:
    global _client
    if _client is None:
        return
    try:
        await _client.aclose()
    except Exception as exc:  # pragma: no cover
        logger.warning("redis.client.close_error: %s", str(exc))
    finally:
        _client = None
        _available = None


async def is_available() -> bool:
    """Cache-friendly liveness ping used by /health."""
    client = get_client()
    if client is None:
        return False
    try:
        return bool(await client.ping())
    except Exception as exc:
        logger.warning("redis.ping.failed: %s", str(exc))
        return False


async def get_json(key: str) -> Optional[Any]:
    client = get_client()
    if client is None:
        return None
    try:
        raw = await client.get(key)
    except Exception as exc:
        logger.warning("redis.get.failed key=%s err=%s", key, str(exc))
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def set_json(key: str, value: Any, ttl_seconds: int = 60) -> bool:
    """Store value as JSON with TTL. Returns True if persisted."""
    client = get_client()
    if client is None:
        return False
    try:
        payload = json.dumps(value, default=str)
        await client.set(key, payload, ex=ttl_seconds)
        return True
    except Exception as exc:
        logger.warning("redis.set.failed key=%s err=%s", key, str(exc))
        return False


async def delete(key: str) -> None:
    client = get_client()
    if client is None:
        return
    try:
        await client.delete(key)
    except Exception as exc:  # pragma: no cover
        logger.warning("redis.delete.failed key=%s err=%s", key, str(exc))