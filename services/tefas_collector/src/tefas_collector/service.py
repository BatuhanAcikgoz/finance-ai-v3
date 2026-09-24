"""TEFAS Collector main service logic."""
from datetime import UTC, datetime
from typing import Any

import asyncpg
import structlog
from redis.asyncio import Redis

from tefas_collector.client import TEFASAPIClient
from tefas_collector.config import settings

logger = structlog.get_logger(__name__)


class TEFASCollectorService:
    """Service for collecting and processing TEFAS fund data."""

    FUND_TYPES = [
        "EQUITY",           # Hisse senedi fonları
        "DEBT",             # Borçlanma araçları fonları
        "PARTICIPATION",    # Katılım fonları
        "GOLD",             # Altın fonları
        "INDEX",            # Endeks fonları
        "VARIABLE",         # Değişken fonlar
        "MONEY_MARKET",     # Para piyasası fonları
        "FOREIGN",          # Yabancı fonlar
        "REIT",             # Gayrimenkul yatırım fonları
        "VENTURE",          # Risk sermayesi fonları
    ]

    def __init__(self) -> None:
        """Initialize TEFAS collector service."""
        self._client = TEFASAPIClient()
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
        await self._client.close()

    async def collect_all_funds(self) -> tuple[int, int]:
        """
        Collect all fund NAVs and details.

        Returns:
            Tuple of (funds_processed, navs_updated)
        """
        funds = await self._client.get_all_funds()
        funds_processed = 0
        navs_updated = 0

        for fund in funds:
            funds_processed += 1
            fund_code = fund.get("fundCode", "")

            # Collect NAV
            try:
                nav_data = await self._client.get_fund_nav(fund_code)
                await self._insert_nav(fund_code, nav_data)
                navs_updated += 1
            except Exception as e:
                logger.warning("nav_fetch_failed", fund_code=fund_code, error=str(e))

            # Collect details
            try:
                details = await self._client.get_fund_details(fund_code)
                await self._insert_fund_details(fund_code, details)
            except Exception as e:
                logger.warning("details_fetch_failed", fund_code=fund_code, error=str(e))

        logger.info(
            "tefas_collection_completed",
            funds_processed=funds_processed,
            navs_updated=navs_updated,
        )

        return funds_processed, navs_updated

    async def collect_daily_flows(self, date: str) -> int:
        """
        Collect daily fund flows for all funds.

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            Number of flow records processed
        """
        funds = await self._client.get_all_funds()
        flows_processed = 0

        for fund in funds:
            fund_code = fund.get("fundCode", "")
            try:
                flows = await self._client.get_fund_flows(fund_code, date)
                await self._insert_flows(fund_code, date, flows)
                flows_processed += 1
            except Exception as e:
                logger.warning("flows_fetch_failed", fund_code=fund_code, error=str(e))

        logger.info("tefas_flows_completed", date=date, flows_processed=flows_processed)
        return flows_processed

    async def _insert_nav(self, fund_code: str, nav_data: dict[str, Any]) -> None:
        """Insert NAV record into database."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        now = datetime.now(UTC).isoformat()

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tefas.navs (
                    fund_code, nav_date, nav_value, nav_change_pct,
                    subscription_price, redemption_price, fund_size,
                    ingested_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (fund_code, nav_date) DO UPDATE SET
                    nav_value = EXCLUDED.nav_value,
                    nav_change_pct = EXCLUDED.nav_change_pct
                """,
                fund_code,
                nav_data.get("date", now),
                nav_data.get("navValue"),
                nav_data.get("changePercent"),
                nav_data.get("subscriptionPrice"),
                nav_data.get("redemptionPrice"),
                nav_data.get("fundSize"),
                now,
            )

    async def _insert_fund_details(self, fund_code: str, details: dict[str, Any]) -> None:
        """Insert fund details into database."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        now = datetime.now(UTC).isoformat()

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tefas.funds (
                    fund_code, fund_name, fund_type, isin_code,
                    manager_name, inception_date, management_fee,
                    min_initial_investment, risk_level, benchmark,
                    investment_strategy, status, ingested_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (fund_code) DO UPDATE SET
                    fund_name = EXCLUDED.fund_name,
                    nav_value = EXCLUDED.nav_value
                """,
                fund_code,
                details.get("fundName"),
                details.get("fundType"),
                details.get("isinCode"),
                details.get("managerName"),
                details.get("inceptionDate"),
                details.get("managementFee"),
                details.get("minInitialInvestment"),
                details.get("riskLevel"),
                details.get("benchmark"),
                details.get("investmentStrategy"),
                details.get("status", "ACTIVE"),
                now,
            )

    async def _insert_flows(
        self, fund_code: str, date: str, flows: dict[str, Any]
    ) -> None:
        """Insert flow record into database."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        now = datetime.now(UTC).isoformat()

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tefas.flows (
                    fund_code, flow_date, subscriptions, redemptions,
                    net_flow, investor_count, ingested_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (fund_code, flow_date) DO UPDATE SET
                    subscriptions = EXCLUDED.subscriptions,
                    redemptions = EXCLUDED.redemptions
                """,
                fund_code,
                date,
                flows.get("subscription"),
                flows.get("redemption"),
                flows.get("netFlow"),
                flows.get("investorCount"),
                now,
            )

    async def run(self) -> None:
        """Run the collector (daily)."""
        await self.initialize()
        logger.info("tefas_collector_started")

        try:
            # Initial collection
            await self.collect_all_funds()

            # Daily flows
            today = datetime.now(UTC).strftime("%Y-%m-%d")
            await self.collect_daily_flows(today)

            logger.info("tefas_initial_collection_completed")
        finally:
            await self.close()
