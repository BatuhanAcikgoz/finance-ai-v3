"""PostgreSQL connection management with asyncpg."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=".env",
        case_sensitive=False,
    )

    host: str = "localhost"
    port: int = 5432
    db: str = "finance_ai_v3"
    user: str = "finance_ai_v3"
    password: str = Field(default="", description="PostgreSQL password - must be set via environment")
    max_connections: int = 20

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if v == "CHANGE_ME":
            raise ValueError("POSTGRES_PASSWORD cannot be 'CHANGE_ME' - must be set to a valid password")
        if not v:
            raise ValueError("POSTGRES_PASSWORD must be set - database password is required")
        return v

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class DatabasePool:
    """Manages PostgreSQL connection pool."""

    def __init__(self, settings: DatabaseSettings):
        self.settings = settings
        self._pool: asyncpg.Pool | None = None

    async def init(self) -> None:
        """Initialize the connection pool."""
        if self._pool is not None:
            return

        self._pool = await asyncpg.create_pool(
            host=self.settings.host,
            port=self.settings.port,
            database=self.settings.db,
            user=self.settings.user,
            password=self.settings.password,
            min_size=5,
            max_size=self.settings.max_connections,
        )

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def acquire(self) -> asyncpg.Connection:
        """Acquire a connection from the pool."""
        if self._pool is None:
            await self.init()
        return await self._pool.acquire()  # type: ignore

    async def release(self, connection: asyncpg.Connection) -> None:
        """Release a connection back to the pool."""
        if self._pool is not None:
            await self._pool.release(connection)

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Context manager for database connections."""
        conn = await self.acquire()
        try:
            yield conn
        finally:
            await self.release(conn)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[asyncpg.Transaction, None]:
        """Context manager for database transactions."""
        async with self.connection() as conn, conn.transaction():
            yield conn


# Global database pool instance
_db_pool: DatabasePool | None = None


def get_db_pool() -> DatabasePool:
    """Get the global database pool instance."""
    global _db_pool
    if _db_pool is None:
        settings = DatabaseSettings()
        _db_pool = DatabasePool(settings)
    return _db_pool


async def init_db() -> None:
    """Initialize the database pool."""
    pool = get_db_pool()
    await pool.init()


async def close_db() -> None:
    """Close the database pool."""
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None
