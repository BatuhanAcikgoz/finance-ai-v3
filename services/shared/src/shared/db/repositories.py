"""Base repository pattern for database access."""

from typing import Any, Generic, TypeVar

import asyncpg

from .connection import get_db_pool

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Base class for all repositories."""

    def __init__(self, table_name: str, schema: str = "public"):
        self.table_name = table_name
        self.schema = schema
        self.pool = get_db_pool()

    @property
    def full_table_name(self) -> str:
        return f"{self.schema}.{self.table_name}"

    async def fetch_one(
        self,
        query: str,
        *args: Any,
    ) -> T | None:
        """Execute a query and return a single result."""
        async with self.pool.connection() as conn:
            result = await conn.fetchrow(query, *args)
            return dict(result) if result else None

    async def fetch_all(
        self,
        query: str,
        *args: Any,
    ) -> list[T]:
        """Execute a query and return all results."""
        async with self.pool.connection() as conn:
            results = await conn.fetch(query, *args)
            return [dict(r) for r in results]

    async def execute(
        self,
        query: str,
        *args: Any,
    ) -> str:
        """Execute a query (INSERT, UPDATE, DELETE)."""
        async with self.pool.connection() as conn:
            return await conn.execute(query, *args)

    async def fetchval(
        self,
        query: str,
        *args: Any,
    ) -> Any:
        """Execute a query and return a single value."""
        async with self.pool.connection() as conn:
            return await conn.fetchval(query, *args)

    async def copy_to(
        self,
        query: str,
        *args: Any,
    ) -> asyncpg.CopyToBuffer:
        """Execute a COPY query."""
        async with self.pool.connection() as conn:
            return await conn.copy_to(query, *args)

    async def copy_from(
        self,
        table: str,
        columns: list[str],
        rows: list[tuple],
    ) -> int:
        """Execute a COPY FROM query."""
        async with self.pool.connection() as conn:
            return await conn.copy_from(table, columns, rows)
