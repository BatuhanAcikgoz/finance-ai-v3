"""Async Postgres pool factory and schema management.

Import-safe: if the database is unreachable, ``get_pool()`` returns ``None`` and
``is_available()`` reports ``False``. Routes use ``with_db`` / ``fetch`` helpers
that no-op gracefully when no pool is present.

Tables follow ``infra/docker/postgres/init.sql`` schemas:
  - market_data.tickers, market_data.bars
  - decision.decisions
We only ``CREATE`` if missing — never destructive.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

import asyncpg

from config import settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None
_lock = asyncio.Lock()
_schema_ready = False


# -- minimal DDL used by ensure_schema() and tests --------------------------
# These are idempotent CREATE IF NOT EXISTS, matching the columns the API
# gateway reads. The full schema with foreign keys / partitions lives in
# infra/docker/postgres/init.sql and runs at first container boot.
SCHEMA_SQL: tuple[str, ...] = (
    """
    CREATE SCHEMA IF NOT EXISTS market_data
    """,
    """
    CREATE SCHEMA IF NOT EXISTS decision
    """,
    """
    CREATE TABLE IF NOT EXISTS market_data.tickers (
        ticker        VARCHAR(5) PRIMARY KEY,
        name          VARCHAR(200) NOT NULL,
        sector        VARCHAR(50),
        subsector     VARCHAR(100),
        is_index      BOOLEAN DEFAULT FALSE,
        is_active     BOOLEAN DEFAULT TRUE,
        discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_data.bars (
        id           BIGSERIAL PRIMARY KEY,
        ticker       VARCHAR(5) NOT NULL,
        timeframe    VARCHAR(5) NOT NULL CHECK (timeframe IN ('1m','5m','15m','60m','1d')),
        open         NUMERIC(18,4) NOT NULL,
        high         NUMERIC(18,4) NOT NULL,
        low          NUMERIC(18,4) NOT NULL,
        close        NUMERIC(18,4) NOT NULL,
        volume       NUMERIC(18,4) NOT NULL,
        bar_start    TIMESTAMPTZ NOT NULL,
        bar_end      TIMESTAMPTZ NOT NULL,
        ingested_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(ticker, timeframe, bar_start)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_bars_ticker_tf_start
        ON market_data.bars(ticker, timeframe, bar_start DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS decision.decisions (
        decision_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        portfolio_id          UUID NOT NULL,
        ticker                VARCHAR(5) NOT NULL,
        action                VARCHAR(25) NOT NULL CHECK (action IN
                              ('BUY','SELL','HOLD','REDUCE','INSUFFICIENT_EVIDENCE')),
        confidence            NUMERIC(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
        position_size_pct     NUMERIC(6,4) CHECK (position_size_pct BETWEEN 0 AND 0.25),
        evidence              JSONB NOT NULL DEFAULT '{}'::jsonb,
        evidence_count        INTEGER NOT NULL DEFAULT 0,
        contradiction_score   NUMERIC(4,3) NOT NULL DEFAULT 0,
        supervisor_reasoning  TEXT,
        portfolio_context     JSONB,
        compliance_status     VARCHAR(10) NOT NULL DEFAULT 'PENDING' CHECK
                              (compliance_status IN ('PENDING','APPROVED','BLOCKED')),
        compliance_reason     TEXT,
        effective_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        data_completeness     VARCHAR(10) NOT NULL DEFAULT 'PARTIAL',
        prompt_versions       JSONB NOT NULL DEFAULT '{}'::jsonb
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_decisions_created_at
        ON decision.decisions(created_at DESC)
    """,
)


async def get_pool() -> Optional[asyncpg.Pool]:
    """Lazily create and return the global asyncpg pool, or ``None`` if down."""
    global _pool, _schema_ready
    if _pool is not None:
        return _pool
    async with _lock:
        if _pool is not None:
            return _pool
        try:
            _pool = await asyncpg.create_pool(
                dsn=settings.async_database_url,
                min_size=1,
                max_size=settings.postgres_max_connections,
                max_inactive_connection_lifetime=60,
                command_timeout=10,
            )
            if _pool is None:
                raise RuntimeError("asyncpg.create_pool returned None")
            logger.info("db.pool.created", host=settings.postgres_host,
                        db=settings.postgres_db)
        except Exception as exc:  # pragma: no cover - connection errors
            logger.warning(
                "db.pool.unavailable host=%s db=%s err=%s",
                settings.postgres_host, settings.postgres_db, str(exc),
            )
            _pool = None
    return _pool


async def close_pool() -> None:
    """Close the pool on shutdown. Safe to call when not initialized."""
    global _pool, _schema_ready
    if _pool is None:
        return
    try:
        await _pool.close()
    except Exception as exc:  # pragma: no cover
        logger.warning("db.pool.close_error: %s", str(exc))
    finally:
        _pool = None
        _schema_ready = False


async def is_available() -> bool:
    """Cheap liveness check used by /health."""
    pool = await get_pool()
    if pool is None:
        return False
    try:
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as exc:
        logger.warning("db.ping.failed: %s", str(exc))
        return False


async def ensure_schema() -> None:
    """Run CREATE TABLE IF NOT EXISTS for the gateway-required tables.

    Safe to call multiple times. If the database is unreachable, logs a
    warning and returns without raising — health endpoint will report
    degraded.
    """
    global _schema_ready
    pool = await get_pool()
    if pool is None:
        logger.warning("db.ensure_schema.skipped reason=pool_unavailable")
        return
    try:
        async with pool.acquire() as conn:
            for stmt in SCHEMA_SQL:
                await conn.execute(stmt)
        _schema_ready = True
        logger.info("db.ensure_schema.ok")
    except Exception as exc:
        logger.warning("db.ensure_schema.failed: %s", str(exc))


@asynccontextmanager
async def acquire() -> AsyncIterator[Optional[asyncpg.Connection]]:
    """Acquire a connection or yield None on failure.

    Usage::

        async with acquire() as conn:
            if conn is None:
                return []
            rows = await conn.fetch("SELECT ...")
    """
    pool = await get_pool()
    if pool is None:
        yield None
        return
    try:
        async with pool.acquire() as conn:
            yield conn
    except Exception as exc:
        logger.warning("db.acquire.error: %s", str(exc))
        yield None


async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    """Convenience: run SELECT and return rows, or [] if pool unavailable."""
    async with acquire() as conn:
        if conn is None:
            return []
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args: Any) -> Optional[asyncpg.Record]:
    """Convenience: run SELECT and return a single row or None."""
    async with acquire() as conn:
        if conn is None:
            return None
        return await conn.fetchrow(query, *args)


async def execute(query: str, *args: Any) -> str:
    """Convenience: run INSERT/UPDATE; returns status string ('' on failure)."""
    async with acquire() as conn:
        if conn is None:
            return ""
        return await conn.execute(query, *args)