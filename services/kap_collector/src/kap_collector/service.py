"""KAP Collector main service logic."""
import hashlib
from datetime import UTC, datetime
from typing import Any

import asyncpg
import structlog
from redis.asyncio import Redis

from kap_collector.client import KAPAPIClient
from kap_collector.config import settings

logger = structlog.get_logger(__name__)


class KAPCollectorService:
    """Service for collecting and processing KAP announcements."""

    def __init__(self) -> None:
        """Initialize KAP collector service."""
        self._client = KAPAPIClient()
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

    async def get_last_poll_time(self) -> str | None:
        """Get the last poll time from Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        return await self._redis.get("kap:last_poll_at")

    async def set_last_poll_time(self, timestamp: str) -> None:
        """Set the last poll time in Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        await self._redis.set("kap:last_poll_at", timestamp)

    def _check_idempotency(self, publishing_id: str, version: str | None = None) -> str:
        """Generate idempotency key."""
        key_parts = [publishing_id]
        if version:
            key_parts.append(version)
        key_string = ":".join(key_parts)
        return f"kap:{hashlib.sha256(key_string.encode()).hexdigest()[:16]}"

    async def _is_duplicate(self, idempotency_key: str) -> bool:
        """Check if this disclosure was already processed."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        return bool(await self._redis.exists(idempotency_key))

    async def _mark_processed(self, idempotency_key: str) -> None:
        """Mark disclosure as processed in Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        await self._redis.setex(
            idempotency_key,
            settings.idempotency_key_ttl_seconds,
            "1",
        )

    async def poll_disclosures(self) -> tuple[int, int, int]:
        """
        Poll KAP API for new disclosures.

        Returns:
            Tuple of (total_processed, new_inserted, material_count)
        """
        last_poll = await self.get_last_poll_time()
        disclosures = await self._client.get_disclosures(since=last_poll)

        total_processed = 0
        new_inserted = 0
        material_count = 0

        for disclosure in disclosures:
            total_processed += 1
            publishing_id = disclosure.get("publishingId", "")

            # Check idempotency
            idempotency_key = self._check_idempotency(publishing_id)
            if await self._is_duplicate(idempotency_key):
                logger.debug("skipping_duplicate", publishing_id=publishing_id)
                continue

            # Fetch full detail
            try:
                detail = await self._client.get_disclosure_detail(publishing_id)
            except Exception as e:
                logger.error(
                    "failed_to_fetch_disclosure_detail",
                    publishing_id=publishing_id,
                    error=str(e),
                )
                continue

            # Process disclosure
            result = await self._process_disclosure(detail)
            if result["inserted"]:
                new_inserted += 1
            if result["is_material"]:
                material_count += 1

            # Mark as processed
            await self._mark_processed(idempotency_key)

        # Update last poll time
        now = datetime.now(UTC).isoformat()
        await self.set_last_poll_time(now)

        logger.info(
            "kap_poll_completed",
            total_processed=total_processed,
            new_inserted=new_inserted,
            material_count=material_count,
        )

        return total_processed, new_inserted, material_count

    async def _process_disclosure(
        self, disclosure: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process a single disclosure record.

        Args:
            disclosure: Full disclosure record from KAP API

        Returns:
            Processing result with insert and material flags
        """
        publishing_id = disclosure.get("publishingId", "")
        title = disclosure.get("title", "")
        body = disclosure.get("content", "") or disclosure.get("summary", "")
        summary = disclosure.get("summary")
        category = self._classify_category(disclosure)
        is_material = self._detect_materiality(disclosure)
        tickers = self._extract_tickers(disclosure)
        published_at = disclosure.get("publishDate", "")

        now = datetime.now(UTC).isoformat()
        source_url = f"https://www.kap.org.tr/tr/Bildir/{publishing_id}"

        # Insert into PostgreSQL
        if self._pool:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kap.disclosures (
                        publishing_id, title, summary, body, category,
                        is_material, published_at, ingested_at, source_url,
                        needs_review, tickers
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (publishing_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        body = EXCLUDED.body
                    """,
                    publishing_id,
                    title,
                    summary,
                    body,
                    category,
                    is_material,
                    published_at,
                    now,
                    source_url,
                    False,  # needs_review
                    tickers,
                )

        # Emit material event to Redis
        if is_material and tickers:
            await self._emit_material_event(disclosure, tickers)

        return {
            "inserted": True,
            "is_material": is_material,
            "publishing_id": publishing_id,
        }

    def _classify_category(self, disclosure: dict[str, Any]) -> str:
        """Classify disclosure into KAP category."""
        # Simple rule-based classification based on disclosure type
        _disclosure_type = disclosure.get("disclosureType", "")
        title_lower = disclosure.get("title", "").lower()

        if "kar" in title_lower or "gelir" in title_lower:
            return "FINANCIAL_REPORT"
        elif "temettü" in title_lower or "dividend" in title_lower:
            return "DIVIDEND"
        elif "birleşme" in title_lower or "devir" in title_lower or "satın alma" in title_lower:
            return "MA"
        elif "yönetim" in title_lower or "kurul" in title_lower:
            return "BOARD_CHANGE"
        elif "sermaye" in title_lower or "artır" in title_lower:
            return "CAPITAL_ACTION"
        elif "genel kurul" in title_lower:
            return "GENERAL_ASSEMBLY"
        elif "denetçi" in title_lower or "bağımsız" in title_lower:
            return "AUDITOR"
        elif "derecelendirme" in title_lower or "rating" in title_lower:
            return "RATING"
        elif "dava" in title_lower or "mahkeme" in title_lower:
            return "LAWSUIT"
        elif "içeriden" in title_lower or "bilgi" in title_lower:
            return "INSIDER_TRADING"
        elif "özellik" in title_lower or "materyal" in title_lower:
            return "MATERIAL_EVENT"
        else:
            return "OTHER"

    def _detect_materiality(self, disclosure: dict[str, Any]) -> bool:
        """Detect if disclosure is material."""
        title_lower = disclosure.get("title", "").lower()
        body_lower = (disclosure.get("content", "") or "").lower()

        # Material keywords in Turkish
        material_keywords = [
            "materyal", "özellik", "önemli", "kritik",
            "kar", "zarar", "büyüme", "düşüş", "yükseliş",
        ]

        for keyword in material_keywords:
            if keyword in title_lower or keyword in body_lower:
                return True

        return False

    def _extract_tickers(self, disclosure: dict[str, Any]) -> list[str]:
        """Extract BIST tickers from disclosure."""
        import re

        text = f"{disclosure.get('title', '')} {disclosure.get('content', '')}"

        # BIST ticker pattern (2-4 uppercase letters, optionally followed by numbers)
        pattern = r"\b([A-ZÇĞİÖŞÜ]{2,4})\b"
        matches = re.findall(pattern, text)

        # Filter to valid BIST tickers (basic filtering)
        valid_tickers = []
        for ticker in matches:
            # Skip common Turkish words that look like tickers
            if ticker not in ["BİST", "KAP", "SPK", "BDDK", "TCMB", "TÜİK"]:
                valid_tickers.append(ticker)

        return list(set(valid_tickers))[:10]  # Limit to 10 tickers

    async def _emit_material_event(
        self, disclosure: dict[str, Any], tickers: list[str]
    ) -> None:
        """Emit material disclosure event to Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")

        event = {
            "event_type": "raw.kap.material",
            "publishing_id": disclosure.get("publishingId"),
            "title": disclosure.get("title"),
            "category": self._classify_category(disclosure),
            "tickers": tickers,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self._redis.publish("raw.kap.material", str(event))

    async def run(self) -> None:
        """Run the collector (continuous polling)."""
        await self.initialize()
        logger.info("kap_collector_started", poll_interval=settings.kap_poll_interval_seconds)

        try:
            while True:
                try:
                    await self.poll_disclosures()
                except Exception as e:
                    logger.error("kap_poll_error", error=str(e))

                import asyncio
                await asyncio.sleep(settings.kap_poll_interval_seconds)
        finally:
            await self.close()
