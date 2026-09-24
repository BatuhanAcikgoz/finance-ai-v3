"""Technical Analysis main service logic."""
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pandas as pd
import structlog
from redis.asyncio import Redis

from technical_analysis.config import settings
from technical_analysis.indicators import TechnicalIndicators

logger = structlog.get_logger(__name__)


class TechnicalAnalysisService:
    """Service for computing technical indicators and detecting signals."""

    def __init__(self) -> None:
        """Initialize technical analysis service."""
        self._redis: Redis | None = None
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        """Initialize Redis and database connections."""
        self._redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
        )

    async def close(self) -> None:
        """Close all connections."""
        if self._redis:
            await self._redis.close()
        if self._pool:
            await self._pool.close()

    def _check_idempotency(self, ticker: str, timeframe: str, close_time: str) -> str:
        """Generate idempotency key."""
        return f"technical:{ticker}:{timeframe}:{close_time}"

    async def _is_duplicate(self, idempotency_key: str) -> bool:
        """Check if this bar was already processed."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        return bool(await self._redis.exists(idempotency_key))

    async def _mark_processed(self, idempotency_key: str) -> None:
        """Mark bar as processed in Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        await self._redis.setex(
            idempotency_key,
            settings.idempotency_key_ttl_seconds,
            "1",
        )

    async def process_bar(self, bar_data: dict[str, Any]) -> dict[str, Any]:
        """
        Process a single bar and compute indicators.

        Args:
            bar_data: Bar data with ticker, timeframe, OHLCV

        Returns:
            Analysis result with indicators and signals
        """
        ticker = bar_data["ticker"]
        timeframe = bar_data["timeframe"]
        close_time = bar_data["bar_end"]

        # Check idempotency
        idempotency_key = self._check_idempotency(ticker, timeframe, close_time)
        if await self._is_duplicate(idempotency_key):
            logger.debug("skipping_duplicate_bar", ticker=ticker, timeframe=timeframe)
            return {"skipped": True, "ticker": ticker, "timeframe": timeframe}

        # Fetch historical bars
        bars = await self._fetch_bars(ticker, timeframe, limit=200)
        if not bars:
            return {"error": "No bars found", "ticker": ticker}

        # Convert to DataFrame
        df = pd.DataFrame(bars)
        closes = df["close"]
        highs = df["high"]
        lows = df["low"]
        volumes = df["volume"]

        # Compute indicators
        indicators = TechnicalIndicators.compute_all(closes, highs, lows, volumes)

        # Determine data completeness
        is_complete = len(bars) >= 200
        data_completeness = "complete" if is_complete else "partial"

        # Prepare result
        result = {
            "ticker": ticker,
            "timeframe": timeframe,
            "bar_time": close_time,
            "indicators": indicators,
            "signals": indicators.get("signals", []),
            "data_completeness": data_completeness,
        }

        # Insert into database
        await self._insert_indicators(result, bar_data)

        # Emit signal events
        for signal in indicators.get("signals", []):
            await self._emit_signal_event(ticker, timeframe, signal)

        # Mark as processed
        await self._mark_processed(idempotency_key)

        logger.info(
            "technical_analysis_completed",
            ticker=ticker,
            timeframe=timeframe,
            signal_count=len(indicators.get("signals", [])),
        )

        return result

    async def _fetch_bars(
        self, ticker: str, timeframe: str, limit: int = 200
    ) -> list[dict[str, Any]]:
        """Fetch historical bars from database."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT open, high, low, close, volume, bar_end
                FROM market_data.bars
                WHERE ticker = $1 AND timeframe = $2
                ORDER BY bar_end DESC
                LIMIT $3
                """,
                ticker,
                timeframe,
                limit,
            )
            return [dict(row) for row in rows]

    async def _insert_indicators(
        self, indicators: dict[str, Any], bar_data: dict[str, Any]
    ) -> None:
        """Insert computed indicators into database."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        ind = indicators["indicators"]

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO analysis.technical_indicators (
                    ticker, timeframe, bar_time, sma_20, sma_50, sma_200,
                    ema_12, ema_26, macd, macd_signal, macd_hist,
                    rsi, stoch_k, stoch_d, williams_r, cci,
                    bb_upper, bb_middle, bb_lower, bb_width, bb_percent,
                    atr, obv, vwap, mfi, cmf,
                    adx, psar, signals, data_completeness,
                    computed_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31)
                ON CONFLICT (ticker, timeframe, bar_time) DO UPDATE SET
                    sma_20 = EXCLUDED.sma_20,
                    sma_50 = EXCLUDED.sma_50,
                    sma_200 = EXCLUDED.sma_200,
                    rsi = EXCLUDED.rsi,
                    signals = EXCLUDED.signals
                """,
                indicators["ticker"],
                indicators["timeframe"],
                indicators["bar_time"],
                ind.get("sma_20"),
                ind.get("sma_50"),
                ind.get("sma_200"),
                ind.get("ema_12"),
                ind.get("ema_26"),
                ind.get("macd"),
                ind.get("macd_signal"),
                ind.get("macd_hist"),
                ind.get("rsi"),
                ind.get("stoch_k"),
                ind.get("stoch_d"),
                ind.get("williams_r"),
                ind.get("cci"),
                ind.get("bb_upper"),
                ind.get("bb_middle"),
                ind.get("bb_lower"),
                ind.get("bb_width"),
                ind.get("bb_percent"),
                ind.get("atr"),
                ind.get("obv"),
                ind.get("vwap"),
                ind.get("mfi"),
                ind.get("cmf"),
                ind.get("adx"),
                ind.get("psar"),
                indicators["signals"],
                indicators["data_completeness"],
                datetime.now(UTC).isoformat(),
            )

    async def _emit_signal_event(
        self, ticker: str, timeframe: str, signal: dict[str, Any]
    ) -> None:
        """Emit technical signal event to Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")

        event = {
            "event_type": "analysis.technical.signal",
            "ticker": ticker,
            "timeframe": timeframe,
            "signal_type": signal.get("type"),
            "direction": signal.get("direction"),
            "strength": signal.get("strength"),
            "description": signal.get("description"),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self._redis.publish("analysis.technical.signal", str(event))
