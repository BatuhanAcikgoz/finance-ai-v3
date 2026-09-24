"""Sector Analysis main service logic."""
import hashlib
from datetime import UTC, datetime
from typing import Any

import asyncpg
import numpy as np
import structlog
from redis.asyncio import Redis

from sector_analysis.config import settings
from sector_analysis.models import (
    SectorAnalysisEvent,
    SectorAnalysisResult,
    SectorBreadth,
    SectorRelativeStrength,
    SectorReturn,
    SectorScore,
    Signal,
)

logger = structlog.get_logger(__name__)


class SectorAnalysisService:
    """Service for analyzing BIST sector performance."""

    def __init__(self) -> None:
        """Initialize sector analysis service."""
        self._redis: Redis | None = None
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        """Initialize Redis and database connections."""
        self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        self._pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)

    async def close(self) -> None:
        """Close all connections."""
        if self._redis:
            await self._redis.close()
        if self._pool:
            await self._pool.close()

    def _check_idempotency(self, date_iso: str) -> str:
        """Generate idempotency key for sector analysis."""
        return f"sector:{hashlib.sha256(date_iso.encode()).hexdigest()[:16]}"

    async def _is_duplicate(self, idempotency_key: str) -> bool:
        """Check if this analysis was already run today."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        return await self._redis.exists(idempotency_key) > 0

    async def _mark_processed(self, idempotency_key: str) -> None:
        """Mark analysis as processed in Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        await self._redis.setex(idempotency_key, settings.idempotency_key_ttl_seconds, "1")

    async def _fetch_sector_data(self, sector: str, days: int) -> list[dict[str, Any]]:
        """Fetch sector index data from database."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT date, close, volume
                FROM market_data.bars
                WHERE ticker = $1 AND timeframe = '1d'
                ORDER BY date DESC
                LIMIT $2
                """,
                sector,
                days,
            )
            return [dict(row) for row in rows]

    async def _compute_returns(self, data: list[dict[str, Any]]) -> SectorReturn:
        """Compute period returns for a sector."""
        if len(data) < 2:
            return SectorReturn(ticker=data[0]["ticker"] if data else "", period_1d=0, period_1w=0, period_1m=0, period_3m=0, period_ytd=0)

        ticker = data[0]["ticker"]
        closes = [d["close"] for d in data]

        def period_return(days: int) -> float:
            if len(closes) <= days:
                return 0.0
            return (closes[0] - closes[days]) / closes[days]

        return SectorReturn(
            ticker=ticker,
            period_1d=period_return(1),
            period_1w=period_return(5),
            period_1m=period_return(22),
            period_3m=period_return(66),
            period_ytd=period_return(len(closes) - 1) if len(closes) > 1 else 0.0,
        )

    async def _compute_breadth(self, sector: str) -> SectorBreadth:
        """Compute breadth (% of constituents above moving averages)."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            # Get constituent tickers for this sector
            rows = await conn.fetch(
                """
                SELECT ticker FROM market_data.constituents
                WHERE sector_index = $1
                """,
                sector,
            )
            tickers = [row["ticker"] for row in rows]

            if not tickers:
                return SectorBreadth(ticker=sector, above_sma50_pct=0.5, above_sma200_pct=0.5)

            above_50 = 0
            above_200 = 0

            for ticker in tickers:
                row = await conn.fetchrow(
                    """
                    SELECT
                        close,
                        AVG(close) OVER (ORDER BY date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) as sma50,
                        AVG(close) OVER (ORDER BY date ROWS BETWEEN 199 PRECEDING AND CURRENT ROW) as sma200
                    FROM market_data.bars
                    WHERE ticker = $1 AND timeframe = '1d'
                    ORDER BY date DESC
                    LIMIT 1
                    """,
                    ticker,
                )
                if row:
                    if row["close"] >= row["sma50"]:
                        above_50 += 1
                    if row["close"] >= row["sma200"]:
                        above_200 += 1

            return SectorBreadth(
                ticker=sector,
                above_sma50_pct=above_50 / len(tickers) if tickers else 0.0,
                above_sma200_pct=above_200 / len(tickers) if tickers else 0.0,
            )

    async def _compute_relative_strength(
        self, sector_data: list[dict[str, Any]], bist100_data: list[dict[str, Any]]
    ) -> SectorRelativeStrength:
        """Compute relative strength vs BIST-100."""
        if not sector_data or not bist100_data:
            return SectorRelativeStrength(ticker=sector_data[0]["ticker"] if sector_data else "", rs_1m=0, rs_3m=0, rs_ytd=0)

        ticker = sector_data[0]["ticker"]
        sector_closes = [d["close"] for d in sector_data]
        bist_closes = [d["close"] for d in bist100_data]

        def rs(days: int) -> float:
            if len(sector_closes) <= days or len(bist_closes) <= days:
                return 0.0
            sector_ret = (sector_closes[0] - sector_closes[days]) / sector_closes[days]
            bist_ret = (bist_closes[0] - bist_closes[days]) / bist_closes[days]
            return sector_ret - bist_ret if bist_ret != 0 else 0.0

        return SectorRelativeStrength(
            ticker=ticker,
            rs_1m=rs(22),
            rs_3m=rs(66),
            rs_ytd=rs(len(sector_closes) - 1) if len(sector_closes) > 1 else 0.0,
        )

    def _compute_momentum_score(self, returns: SectorReturn) -> float:
        """Compute momentum score from returns."""
        # Weight recent returns more heavily
        score = (
            returns.period_1d * 0.1
            + returns.period_1w * 0.2
            + returns.period_1m * 0.3
            + returns.period_3m * 0.3
            + returns.period_ytd * 0.1
        )
        # Normalize to 0-1 range (rough)
        return max(0.0, min(1.0, 0.5 + score * 5))

    def _compute_breadth_score(self, breadth: SectorBreadth) -> float:
        """Compute breadth score."""
        return (breadth.above_sma50_pct + breadth.above_sma200_pct) / 2

    def _compute_rs_score(self, rs: SectorRelativeStrength) -> float:
        """Compute relative strength score."""
        avg_rs = (rs.rs_1m + rs.rs_3m + rs.rs_ytd) / 3
        # Normalize: positive RS = score > 0.5
        return max(0.0, min(1.0, 0.5 + avg_rs * 2))

    def _compute_total_score(
        self, momentum: float, breadth: float, rs: float
    ) -> tuple[float, Signal]:
        """Compute total sector score and signal."""
        total = momentum * 0.4 + breadth * 0.3 + rs * 0.3

        if total >= 0.65:
            signal = Signal.BULLISH
        elif total <= 0.35:
            signal = Signal.BEARISH
        else:
            signal = Signal.NEUTRAL

        return total, signal

    async def _insert_sector_analysis(
        self, sector_scores: list[SectorScore], is_weekly: bool
    ) -> None:
        """Insert sector analysis into PostgreSQL."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            for score in sector_scores:
                await conn.execute(
                    """
                    INSERT INTO analysis.sector_analyses
                    (analysis_id, ticker, total_score, momentum_score, breadth_score,
                     rs_score, rank, signal, is_weekly_update, analyzed_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (ticker, analyzed_at::date) DO UPDATE SET
                        total_score = EXCLUDED.total_score,
                        momentum_score = EXCLUDED.momentum_score,
                        breadth_score = EXCLUDED.breadth_score,
                        rs_score = EXCLUDED.rs_score,
                        rank = EXCLUDED.rank,
                        signal = EXCLUDED.signal
                    """,
                    f"{score.ticker}_{datetime.now(UTC).date().isoformat()}",
                    score.ticker,
                    score.total_score,
                    score.momentum_score,
                    score.breadth_score,
                    score.relative_strength_score,
                    score.rank,
                    score.signal.value,
                    is_weekly,
                    datetime.now(UTC),
                )

    async def _insert_correlation_matrix(
        self, correlation_matrix: list[list[float]], tickers: list[str]
    ) -> None:
        """Insert correlation matrix into PostgreSQL."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO analysis.sector_correlations
                (correlation_id, tickers, correlation_matrix, computed_at)
                VALUES ($1, $2, $3, $4)
                """,
                f"corr_{datetime.now(UTC).date().isoformat()}",
                tickers,
                correlation_matrix,
                datetime.now(UTC),
            )

    async def _emit_complete_event(
        self, analysis_id: str, top_sectors: list[str], bottom_sectors: list[str], is_weekly: bool
    ) -> None:
        """Emit sector analysis complete event to Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        event = SectorAnalysisEvent(
            analysis_id=analysis_id,
            analyzed_at=datetime.now(UTC).isoformat(),
            top_sectors=top_sectors,
            bottom_sectors=bottom_sectors,
            is_weekly_update=is_weekly,
        )
        await self._redis.publish("analysis.sector.complete", event.model_dump_json())

    async def run_daily_analysis(self, is_weekly: bool = False) -> SectorAnalysisResult:
        """
        Run daily sector analysis for all BIST sectors.

        Args:
            is_weekly: If True, also compute and store correlation matrix.

        Returns:
            SectorAnalysisResult with scores for all sectors.
        """
        today_iso = datetime.now(UTC).date().isoformat()
        idempotency_key = self._check_idempotency(today_iso)

        if await self._is_duplicate(idempotency_key):
            logger.info("sector_analysis_already_run_today", date=today_iso)
            # Return cached result from Redis
            cached = await self._redis.get(f"sector:result:{today_iso}")
            if cached:
                return SectorAnalysisResult.model_validate_json(cached)

        await self.initialize()

        try:
            # Fetch BIST-100 data for relative strength calculation
            bist100_data = await self._fetch_sector_data("XU100", settings.lookback_days)

            sector_scores: list[SectorScore] = []
            all_returns: dict[str, list[float]] = {}

            # Analyze each sector
            for sector in settings.bist_sectors:
                try:
                    sector_data = await self._fetch_sector_data(sector, settings.lookback_days)
                    if len(sector_data) < 22:
                        logger.warning("insufficient_data_for_sector", sector=sector)
                        continue

                    # Compute metrics
                    returns = await self._compute_returns(sector_data)
                    breadth = await self._compute_breadth(sector)
                    rs = await self._compute_relative_strength(sector_data, bist100_data)

                    # Compute scores
                    momentum_score = self._compute_momentum_score(returns)
                    breadth_score = self._compute_breadth_score(breadth)
                    rs_score = self._compute_rs_score(rs)
                    total_score, signal = self._compute_total_score(momentum_score, breadth_score, rs_score)

                    sector_scores.append(
                        SectorScore(
                            ticker=sector,
                            total_score=total_score,
                            momentum_score=momentum_score,
                            breadth_score=breadth_score,
                            relative_strength_score=rs_score,
                            rank=0,  # Will be set after sorting
                            signal=signal,
                        )
                    )

                    all_returns[sector] = [d["close"] for d in sector_data]

                except Exception as e:
                    logger.error("sector_analysis_failed", sector=sector, error=str(e))

            # Sort by total score and assign ranks
            sector_scores.sort(key=lambda x: x.total_score, reverse=True)
            for i, score in enumerate(sector_scores):
                score.rank = i + 1

            # Compute correlation matrix if weekly
            correlation_matrix = None
            if is_weekly and len(all_returns) >= 2:
                try:
                    # Build price matrix
                    min_len = min(len(returns) for returns in all_returns.values())
                    price_matrix = np.array([returns[:min_len] for returns in all_returns.values()])
                    correlation_matrix = np.corrcoef(price_matrix).tolist()
                    tickers = list(all_returns.keys())
                    await self._insert_correlation_matrix(correlation_matrix, tickers)
                except Exception as e:
                    logger.error("correlation_matrix_failed", error=str(e))

            # Insert results
            await self._insert_sector_analysis(sector_scores, is_weekly)

            # Build result
            result = SectorAnalysisResult(
                analysis_id=f"sector_{today_iso}",
                analyzed_at=datetime.now(UTC).isoformat(),
                sector_scores=sector_scores,
                correlation_matrix=correlation_matrix,
                is_weekly_correlation_update=is_weekly,
                data_completeness="complete" if len(sector_scores) == len(settings.bist_sectors) else "partial",
            )

            # Cache result
            if self._redis:
                await self._redis.setex(f"sector:result:{today_iso}", 86400, result.model_dump_json())

            # Emit event
            top_3 = [s.ticker for s in sector_scores[:3]]
            bottom_3 = [s.ticker for s in sector_scores[-3:]]
            await self._emit_complete_event(result.analysis_id, top_3, bottom_3, is_weekly)

            await self._mark_processed(idempotency_key)

            logger.info("sector_analysis_complete", sectors=len(sector_scores), is_weekly=is_weekly)
            return result

        finally:
            await self.close()

    async def run(self) -> None:
        """Run the service as a scheduled job."""
        logger.info("sector_analysis_service_started")
        while True:
            now = datetime.now(UTC)
            # Run daily at 18:30 TRT (15:30 UTC)
            target_hour = 15
            target_minute = 30

            if now.hour == target_hour and now.minute >= target_minute:
                # Check if it's Monday for weekly correlation
                is_monday = now.weekday() == 0
                try:
                    await self.run_daily_analysis(is_weekly=is_monday)
                except Exception as e:
                    logger.error("daily_analysis_failed", error=str(e))

            # Sleep 5 minutes before next check
            import asyncio
            await asyncio.sleep(300)
