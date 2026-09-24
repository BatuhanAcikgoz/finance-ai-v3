"""News Analysis main service logic."""
import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

import asyncpg
import structlog
from redis.asyncio import Redis

from news_analysis.client import LiteLLMClient
from news_analysis.config import settings
from news_analysis.models import (
    DataCompleteness,
    Materiality,
    NewsAnalysisResult,
    Topic,
)

logger = structlog.get_logger(__name__)


class NewsAnalysisService:
    """Service for running news analysis on news articles."""

    # Valid BIST ticker pattern
    TICKER_PATTERN = re.compile(r"\b([A-ZÇĞİÖŞÜ]{2,5})\b")

    def __init__(self) -> None:
        """Initialize news analysis service."""
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

    def _check_idempotency(self, article_id: str) -> str:
        """Generate idempotency key."""
        return f"news:{hashlib.sha256(article_id.encode()).hexdigest()[:16]}"

    async def _is_duplicate(self, idempotency_key: str) -> bool:
        """Check if this article was already processed."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        return await self._redis.exists(idempotency_key) > 0

    async def _mark_processed(self, idempotency_key: str) -> None:
        """Mark article as processed in Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        await self._redis.setex(
            idempotency_key,
            settings.idempotency_key_ttl_seconds,
            "1",
        )

    async def _fetch_article(self, article_id: str) -> dict[str, Any] | None:
        """Fetch article from database."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT article_id, title, body, source, url, published_at
                FROM news.articles
                WHERE article_id = $1
                """,
                article_id,
            )
            if row:
                return dict(row)
            return None

    async def _extract_tickers_regex(self, text: str) -> list[str]:
        """Extract potential tickers using regex."""
        matches = self.TICKER_PATTERN.findall(text)

        # Filter out common Turkish words that look like tickers
        skip_words = {
            "BİST", "KAP", "SPK", "BDDK", "TCMB", "TÜİK", "BES",
            "TL", "TRY", "USD", "EUR", "GBP", "FAİZ", "KUR",
        }
        return [m for m in matches if m not in skip_words]

    async def _insert_analysis(
        self, result: NewsAnalysisResult
    ) -> None:
        """Insert analysis result into PostgreSQL."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO analysis.news_analyses (
                    analysis_id, article_id, tickers, topic, materiality,
                    summary_tr, key_entities, confidence, data_completeness,
                    truncated, analysis_timestamp
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (article_id) DO UPDATE SET
                    topic = EXCLUDED.topic,
                    materiality = EXCLUDED.materiality
                """,
                result.analysis_timestamp.isoformat() + "_" + result.article_id,
                result.article_id,
                result.tickers,
                result.topic.value,
                result.materiality.value,
                result.summary_tr,
                result.key_entities,
                result.confidence,
                result.data_completeness.value,
                result.truncated,
                result.analysis_timestamp,
            )

    async def _emit_complete_event(
        self, result: NewsAnalysisResult
    ) -> None:
        """Emit analysis complete event to Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")

        event = {
            "event_type": "analysis.news.complete",
            "article_id": result.article_id,
            "tickers": result.tickers,
            "topic": result.topic.value,
            "materiality": result.materiality.value,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self._redis.publish("analysis.news.complete", str(event))

    async def analyze_article(
        self,
        article_id: str,
        title: str,
        body: str,
        source: str,
    ) -> NewsAnalysisResult | None:
        """
        Analyze a news article.

        Args:
            article_id: Unique article identifier
            title: Article title
            body: Article body
            source: News source

        Returns:
            NewsAnalysisResult or None if skipped/failed
        """
        # Check idempotency
        idempotency_key = self._check_idempotency(article_id)
        if await self._is_duplicate(idempotency_key):
            logger.info("skipping_duplicate", article_id=article_id)
            return None

        # Fallback for short articles
        if len(body) < 100:
            return NewsAnalysisResult(
                article_id=article_id,
                topic=Topic.MACRO,
                materiality=Materiality.LOW,
                summary_tr="Kısa haber.",
                confidence=0.3,
                data_completeness=DataCompleteness.PARTIAL,
            )

        # Call LLM for analysis
        try:
            llm_result, truncated = await self._llm_client.analyze(
                article_id=article_id,
                title=title,
                body=body,
                source=source,
            )
        except Exception as e:
            logger.error(
                "llm_analysis_failed",
                article_id=article_id,
                error=str(e),
            )
            # Fallback to regex-only extraction
            tickers = await self._extract_tickers_regex(f"{title} {body}")
            return NewsAnalysisResult(
                article_id=article_id,
                tickers=tickers[:10],
                topic=Topic.MACRO,
                materiality=Materiality.LOW,
                summary_tr="Haber analiz edilemedi.",
                confidence=0.1,
                data_completeness=DataCompleteness.MISSING,
            )

        # Parse LLM response
        meta = llm_result.get("_meta", {})

        result = NewsAnalysisResult(
            article_id=article_id,
            tickers=llm_result.get("tickers", [])[:10],
            topic=Topic(llm_result.get("topic", "MACRO")),
            materiality=Materiality(llm_result.get("materiality", "LOW")),
            summary_tr=llm_result.get("summary_tr", ""),
            key_entities=llm_result.get("key_entities", []),
            confidence=float(llm_result.get("confidence", 0.5)),
            data_completeness=DataCompleteness(llm_result.get("data_completeness", "partial")),
            truncated=truncated,
            llm_tokens_in=meta.get("tokens_in"),
            llm_tokens_out=meta.get("tokens_out"),
            cost_usd=meta.get("cost_usd"),
        )

        # Insert into database
        try:
            await self._insert_analysis(result)
        except Exception as e:
            logger.error("db_insert_failed", article_id=article_id, error=str(e))

        # Emit complete event
        try:
            await self._emit_complete_event(result)
        except Exception as e:
            logger.error("redis_publish_failed", article_id=article_id, error=str(e))

        # Mark as processed
        await self._mark_processed(idempotency_key)

        logger.info(
            "news_analysis_complete",
            article_id=article_id,
            topic=result.topic.value,
            materiality=result.materiality.value,
        )

        return result

    async def run(self) -> None:
        """Run the service (listen for Redis events)."""
        await self.initialize()
        logger.info("news_analysis_service_started")

        if not self._redis:
            raise RuntimeError("Redis not initialized")

        try:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe("raw.news.new")

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                try:
                    data = json.loads(message["data"])
                    event_type = data.get("event_type", "")

                    if event_type == "raw.news.new":
                        # Fetch full article
                        article = await self._fetch_article(data["article_id"])
                        if article:
                            await self.analyze_article(
                                article_id=article["article_id"],
                                title=article["title"],
                                body=article["body"],
                                source=article["source"],
                            )
                except json.JSONDecodeError:
                    logger.error("invalid_json_message", data=message["data"])
                except Exception as e:
                    logger.error("event_processing_error", error=str(e))
        finally:
            await self.close()
