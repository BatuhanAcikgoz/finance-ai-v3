"""Macro Analysis main service logic."""
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import asyncpg
import structlog
from redis.asyncio import Redis

from macro_analysis.client import LiteLLMClient
from macro_analysis.config import settings
from macro_analysis.models import (
    DataCompleteness,
    ImpactEstimates,
    MacroAnalysisResult,
    Regime,
    Source,
)

logger = structlog.get_logger(__name__)


class MacroAnalysisService:
    """Service for running macro analysis on TCMB/TÜİK/BDDK releases."""

    def __init__(self) -> None:
        """Initialize macro analysis service."""
        self._llm_client = LiteLLMClient()
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

    def _check_idempotency(self, source: str, indicator_code: str, release_date: str) -> str:
        """Generate idempotency key."""
        key_string = f"{source}:{indicator_code}:{release_date}"
        return f"macro:{hashlib.sha256(key_string.encode()).hexdigest()[:16]}"

    async def _is_duplicate(self, idempotency_key: str) -> bool:
        """Check if this release was already processed."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        return await self._redis.exists(idempotency_key) > 0

    async def _mark_processed(self, idempotency_key: str) -> None:
        """Mark release as processed in Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        await self._redis.setex(
            idempotency_key,
            settings.idempotency_key_ttl_seconds,
            "1",
        )

    async def _fetch_indicator_history(
        self, indicator_code: str
    ) -> list[dict[str, Any]]:
        """Fetch 12-month history for an indicator."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT indicator_code, value, unit, release_date
                FROM market_data.macro_indicators
                WHERE indicator_code = $1
                ORDER BY release_date DESC
                LIMIT 12
                """,
                indicator_code,
            )
            return [dict(row) for row in rows]

    async def _insert_analysis(
        self, result: MacroAnalysisResult
    ) -> None:
        """Insert analysis result into PostgreSQL."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO analysis.macro_analyses (
                    analysis_id, indicator_code, source, release_date,
                    actual_value, consensus_value, surprise, regime, regime_changed,
                    impact_estimates, confidence, reasoning, data_completeness,
                    analysis_timestamp
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                ON CONFLICT (indicator_code, release_date) DO UPDATE SET
                    regime = EXCLUDED.regime,
                    confidence = EXCLUDED.confidence
                """,
                result.analysis_timestamp.isoformat() + "_" + result.indicator_code,
                result.indicator_code,
                result.source.value,
                result.release_date,
                result.actual_value,
                result.consensus_value,
                result.surprise,
                result.regime.value,
                result.regime_changed,
                json.dumps(result.impact_estimates.model_dump()),
                result.confidence,
                result.reasoning,
                result.data_completeness.value,
                result.analysis_timestamp,
            )

    async def _emit_complete_event(
        self, result: MacroAnalysisResult
    ) -> None:
        """Emit analysis complete event to Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")

        event = {
            "event_type": "analysis.macro.complete",
            "indicator_code": result.indicator_code,
            "source": result.source.value,
            "regime": result.regime.value,
            "confidence": result.confidence,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self._redis.publish("analysis.macro.complete", str(event))

    async def analyze_macro(
        self,
        indicator_code: str,
        source: str,
        value: float,
        unit: str,
        release_date: str,
    ) -> MacroAnalysisResult | None:
        """
        Analyze a macro indicator release.

        Args:
            indicator_code: TCMB/TÜİK/BDDK indicator code
            source: Data source (TCMB, TUIKS, BDDK)
            value: Released value
            unit: Unit of measurement
            release_date: Release date

        Returns:
            MacroAnalysisResult or None if skipped/failed
        """
        # Check idempotency
        idempotency_key = self._check_idempotency(source, indicator_code, release_date)
        if await self._is_duplicate(idempotency_key):
            logger.info(
                "skipping_duplicate",
                source=source,
                indicator_code=indicator_code,
                release_date=release_date,
            )
            return None

        # Fetch 12-month history
        history = await self._fetch_indicator_history(indicator_code)

        # Call LLM for analysis
        try:
            llm_result = await self._llm_client.analyze(
                indicator_code=indicator_code,
                source=source,
                actual_value=value,
                release_date=release_date,
                history=history,
            )
        except Exception as e:
            logger.error(
                "llm_analysis_failed",
                indicator_code=indicator_code,
                error=str(e),
            )
            # Return insufficient evidence result
            return MacroAnalysisResult(
                indicator_code=indicator_code,
                source=Source(source),
                release_date=datetime.fromisoformat(release_date),
                actual_value=value,
                regime=Regime.RANGE,
                regime_changed=False,
                impact_estimates=ImpactEstimates(
                    bist100_1d_pct=0.0,
                    usdtry_1d_pct=0.0,
                    banking_sector_1d_pct=0.0,
                ),
                confidence=0.0,
                reasoning="LLM analysis failed",
                data_completeness=DataCompleteness.MISSING,
            )

        # Parse LLM response
        meta = llm_result.get("_meta", {})
        impact = llm_result.get("impact_estimates", {})

        result = MacroAnalysisResult(
            indicator_code=indicator_code,
            source=Source(source),
            release_date=datetime.fromisoformat(release_date),
            actual_value=value,
            consensus_value=llm_result.get("consensus_value"),
            surprise=llm_result.get("surprise"),
            regime=Regime(llm_result.get("regime", "RANGE")),
            regime_changed=bool(llm_result.get("regime_changed", False)),
            impact_estimates=ImpactEstimates(
                bist100_1d_pct=float(impact.get("bist100_1d_pct", 0.0)),
                usdtry_1d_pct=float(impact.get("usdtry_1d_pct", 0.0)),
                banking_sector_1d_pct=float(impact.get("banking_sector_1d_pct", 0.0)),
            ),
            confidence=float(llm_result.get("confidence", 0.0)),
            reasoning=llm_result.get("reasoning", ""),
            data_completeness=DataCompleteness(llm_result.get("data_completeness", "partial")),
            llm_tokens_in=meta.get("tokens_in"),
            llm_tokens_out=meta.get("tokens_out"),
            cost_usd=meta.get("cost_usd"),
        )

        # Insert into database
        try:
            await self._insert_analysis(result)
        except Exception as e:
            logger.error("db_insert_failed", indicator_code=indicator_code, error=str(e))

        # Emit complete event
        try:
            await self._emit_complete_event(result)
        except Exception as e:
            logger.error("redis_publish_failed", indicator_code=indicator_code, error=str(e))

        # Mark as processed
        await self._mark_processed(idempotency_key)

        logger.info(
            "macro_analysis_complete",
            indicator_code=indicator_code,
            regime=result.regime.value,
            confidence=result.confidence,
        )

        return result

    async def run(self) -> None:
        """Run the service (listen for Redis events)."""
        await self.initialize()
        logger.info("macro_analysis_service_started")

        if not self._redis:
            raise RuntimeError("Redis not initialized")

        try:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe("raw.macro.update")

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                try:
                    data = json.loads(message["data"])
                    event_type = data.get("event_type", "")

                    if event_type == "raw.macro.update":
                        await self.analyze_macro(
                            indicator_code=data["indicator_code"],
                            source=data["source"],
                            value=data["value"],
                            unit=data["unit"],
                            release_date=data["release_date"],
                        )
                except json.JSONDecodeError:
                    logger.error("invalid_json_message", data=message["data"])
                except Exception as e:
                    logger.error("event_processing_error", error=str(e))
        finally:
            await self.close()
