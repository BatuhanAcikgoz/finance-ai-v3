"""Redis client with connection management and pub/sub support."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta

from pydantic_settings import BaseSettings, SettingsConfigDict

import redis.asyncio as redis


class RedisSettings(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=".env",
        case_sensitive=False,
    )

    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0
    decode_responses: bool = True

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class RedisClient:
    """Async Redis client wrapper."""

    def __init__(self, settings: RedisSettings):
        self.settings = settings
        self._client: redis.Redis | None = None

    async def init(self) -> None:
        """Initialize the Redis connection."""
        if self._client is None:
            self._client = redis.Redis(
                host=self.settings.host,
                port=self.settings.port,
                password=self.settings.password if self.settings.password else None,
                db=self.settings.db,
                decode_responses=self.settings.decode_responses,
            )

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("Redis client not initialized. Call init() first.")
        return self._client

    # Basic operations
    async def get(self, key: str) -> str | None:
        return await self.client.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        px: int | None = None,
        ttl: timedelta | None = None,
    ) -> bool:
        if ttl:
            return await self.client.setex(key, int(ttl.total_seconds()), value)
        return await self.client.set(key, value, ex=ex, px=px)

    async def delete(self, *keys: str) -> int:
        return await self.client.delete(*keys)

    async def exists(self, key: str) -> bool:
        return await self.client.exists(key) > 0

    async def expire(self, key: str, seconds: int) -> bool:
        return await self.client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        return await self.client.ttl(key)

    # JSON operations
    async def get_json(self, key: str) -> dict | None:
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None

    async def set_json(
        self,
        key: str,
        value: dict,
        ex: int | None = None,
        ttl: timedelta | None = None,
    ) -> bool:
        return await self.set(key, json.dumps(value), ex=ex, ttl=ttl)

    # Pub/Sub
    async def publish(self, channel: str, message: str | dict) -> int:
        if isinstance(message, dict):
            message = json.dumps(message)
        return await self.client.publish(channel, message)

    @asynccontextmanager
    async def subscribe(self, *channels: str) -> AsyncGenerator[redis.PubSub, None]:
        pubsub = self.client.pubsub()
        await pubsub.subscribe(*channels)
        try:
            yield pubsub
        finally:
            await pubsub.unsubscribe(*channels)
            await pubsub.close()

    # Stream operations
    async def xadd(
        self,
        stream: str,
        fields: dict[str, str],
        maxlen: int | None = None,
    ) -> str:
        if maxlen:
            return await self.client.xadd(stream, fields, maxlen=maxlen, approximate=True)
        return await self.client.xadd(stream, fields)

    async def xread(
        self,
        streams: dict[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> list:
        return await self.client.xread(streams, count=count, block=block)

    async def xgroup_create(
        self,
        stream: str,
        group: str,
        id: str = "0",
        mkstream: bool = True,
    ) -> bool:
        try:
            await self.client.xgroup_create(stream, group, id, mkstream=mkstream)
            return True
        except redis.ResponseError:
            return False  # Group already exists

    async def xreadgroup(
        self,
        group: str,
        consumer: str,
        streams: dict[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> list:
        return await self.client.xreadgroup(group, consumer, streams, count=count, block=block)

    # Idempotency key operations
    async def is_idempotent(self, key: str) -> bool:
        """Check if an idempotency key exists."""
        return await self.exists(f"idempotency:{key}")

    async def set_idempotent(self, key: str, ttl_seconds: int = 86400) -> bool:
        """Set an idempotency key with 24h TTL."""
        return await self.set(f"idempotency:{key}", "1", ex=ttl_seconds)


# Global Redis client instance
_redis_client: RedisClient | None = None


def get_redis() -> RedisClient:
    """Get the global Redis client instance."""
    global _redis_client
    if _redis_client is None:
        settings = RedisSettings()
        _redis_client = RedisClient(settings)
    return _redis_client
