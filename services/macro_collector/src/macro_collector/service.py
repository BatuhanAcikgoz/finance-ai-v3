"""Macro Collector main service logic."""
from datetime import UTC, datetime, timedelta

import asyncpg
import structlog
from redis.asyncio import Redis

from macro_collector.client import BDDKClient, TCMBEVDSClient, TUICKClient
from macro_collector.config import settings

logger = structlog.get_logger(__name__)


class MacroCollectorService:
    """Service for collecting macroeconomic data from TCMB, TÜİK, BDDK."""

    # TCMB Indicator Codes
    TCMB_INDICATORS = {
        "TP_DK_USD_A": "USD/TRY Exchange Rate",
        "TP_DK_EUR_A": "EUR/TRY Exchange Rate",
        "TP_KKH_TL": "Commercial Interest Rate (TL)",
        "TP_KKH_USD": "Commercial Interest Rate (USD)",
        "TP_KKTF_KK": "Consumer Interest Rate",
        "TP_GAB_MG": "M2 Money Supply",
        "TP_DK_USD_B": "USD/TRY (Banknote)",
        "TP_RES_TCMB": "TCMB Reserves",
    }

    def __init__(self) -> None:
        """Initialize macro collector service."""
        self._tcmb_client = TCMBEVDSClient()
        self._tuik_client = TUICKClient()
        self._bddk_client = BDDKClient()
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
        await self._tcmb_client.close()
        await self._tuik_client.close()
        await self._bddk_client.close()

    async def collect_tcmb_indicators(self) -> int:
        """
        Collect TCMB EVDS indicators.

        Returns:
            Number of indicators collected
        """
        collected = 0
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        start_date = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")

        for series_code in self.TCMB_INDICATORS.keys():
            try:
                data = await self._tcmb_client.get_indicator(series_code, start_date, today)
                for record in data:
                    await self._insert_macro_indicator(
                        indicator_code=series_code,
                        source="TCMB",
                        value=record.get("value"),
                        unit=self._infer_unit(series_code),
                        release_date=record.get("date", today),
                    )
                    collected += 1
            except Exception as e:
                logger.error("tcmb_fetch_failed", series_code=series_code, error=str(e))

        logger.info("tcmb_collection_completed", collected=collected)
        return collected

    async def collect_tuik_indicators(self) -> int:
        """
        Collect TÜİK indicators (CPI, PPI, Unemployment, GDP).

        Returns:
            Number of indicators collected
        """
        collected = 0
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        indicators = [
            ("CPI", self._tuik_client.get_cpi),
            ("PPI", self._tuik_client.get_ppi),
            ("UNEMPLOYMENT", self._tuik_client.get_unemployment),
            ("GDP", self._tuik_client.get_gdp),
        ]

        for indicator_code, fetcher in indicators:
            try:
                data = await fetcher()
                await self._insert_macro_indicator(
                    indicator_code=indicator_code,
                    source="TUIK",
                    value=data.get("value"),
                    unit=self._infer_unit(indicator_code),
                    release_date=today,
                )
                collected += 1
            except Exception as e:
                logger.error("tuik_fetch_failed", indicator_code=indicator_code, error=str(e))

        logger.info("tuik_collection_completed", collected=collected)
        return collected

    async def collect_bddk_indicators(self) -> int:
        """
        Collect BDDK indicators (NPL ratio, capital adequacy).

        Returns:
            Number of indicators collected
        """
        collected = 0
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        indicators = [
            ("NPL_RATIO", self._bddk_client.get_npl_ratio),
            ("CAPITAL_ADEQUACY", self._bddk_client.get_capital_adequacy),
        ]

        for indicator_code, fetcher in indicators:
            try:
                data = await fetcher()
                await self._insert_macro_indicator(
                    indicator_code=indicator_code,
                    source="BDDK",
                    value=data.get("value"),
                    unit=data.get("unit", "percent"),
                    release_date=today,
                )
                collected += 1
            except Exception as e:
                logger.error("bddk_fetch_failed", indicator_code=indicator_code, error=str(e))

        logger.info("bddk_collection_completed", collected=collected)
        return collected

    async def collect_all(self) -> dict[str, int]:
        """
        Collect all macro indicators.

        Returns:
            Dictionary with counts per source
        """
        results = {}

        results["tcmb"] = await self.collect_tcmb_indicators()
        results["tuik"] = await self.collect_tuik_indicators()
        results["bddk"] = await self.collect_bddk_indicators()

        logger.info("macro_collection_completed", results=results)
        return results

    async def _insert_macro_indicator(
        self,
        indicator_code: str,
        source: str,
        value: float | None,
        unit: str,
        release_date: str,
        revised_from: float | None = None,
    ) -> None:
        """Insert macro indicator into database."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        now = datetime.now(UTC).isoformat()

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO market_data.macro_indicators (
                    indicator_code, source, value, unit,
                    release_date, revised_from, ingested_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (indicator_code, source, release_date) DO UPDATE SET
                    value = EXCLUDED.value,
                    revised_from = COALESCE(EXCLUDED.revised_from, market_data.macro_indicators.value)
                """,
                indicator_code,
                source,
                value,
                unit,
                release_date,
                revised_from,
                now,
            )

    def _infer_unit(self, indicator_code: str) -> str:
        """Infer unit from indicator code."""
        if "USD" in indicator_code or "EUR" in indicator_code:
            return "TRY"
        elif "RATE" in indicator_code or "RATIO" in indicator_code:
            return "percent"
        elif "M2" in indicator_code or "GSYIH" in indicator_code or "GDP" in indicator_code:
            return "billion TRY"
        else:
            return "index"

    async def run(self) -> None:
        """Run the collector."""
        await self.initialize()
        logger.info("macro_collector_started")

        try:
            await self.collect_all()
        finally:
            await self.close()
