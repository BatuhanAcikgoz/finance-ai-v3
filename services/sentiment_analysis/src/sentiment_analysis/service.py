"""Sentiment Analysis main service logic."""
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import asyncpg
import structlog
from redis.asyncio import Redis

from sentiment_analysis.config import settings

logger = structlog.get_logger(__name__)


class SentimentAnalysisService:
    """Service for running sentiment analysis on news articles."""

    def __init__(self) -> None:
        """Initialize sentiment analysis service."""
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

    def _check_idempotency(self, article_id: str) -> str:
        """Generate idempotency key."""
        return f"sentiment:{hashlib.sha256(article_id.encode()).hexdigest()[:16]}"

    async def _is_duplicate(self, idempotency_key: str) -> bool:
        """Check if this article was already processed."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        return await self._redis.exists(idempotency_key) > 0

    async def _mark_processed(self, idempotency_key: str) -> None:
        """Mark article as processed in Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        await self._redis.setex(idempotency_key, settings.idempotency_key_ttl_seconds, "1")

    async def _fetch_article(self, article_id: str) -> dict[str, Any] | None:
        """Fetch article from database."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT article_id, title, summary_tr FROM news.articles WHERE article_id = $1",
                article_id,
            )
            return dict(row) if row else None

    async def _insert_sentiment(
        self, article_id: str, ticker: str, sentiment: float, conviction: float
    ) -> None:
        """Insert sentiment analysis into PostgreSQL."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO analysis.sentiment_analyses 
                (analysis_id, article_id, ticker, sentiment, conviction, analyzed_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (article_id, ticker) DO UPDATE SET
                    sentiment = EXCLUDED.sentiment,
                    conviction = EXCLUDED.conviction
                """,
                f"{article_id}_{ticker}",
                article_id,
                ticker,
                sentiment,
                conviction,
                datetime.now(UTC),
            )

    async def _update_daily_aggregate(self, ticker: str, sentiment: float, conviction: float) -> None:
        """Update daily sentiment aggregate in Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        key = f"sentiment:{ticker}:daily:{datetime.now(UTC).date().isoformat()}"
        
        # Get current aggregate
        current = await self._redis.hgetall(key)
        count = int(current.get("count", 0)) + 1
        weighted_sum = float(current.get("weighted_sum", 0.0)) + (sentiment * conviction)
        total_conviction = float(current.get("total_conviction", 0.0)) + conviction
        
        avg_sentiment = weighted_sum / total_conviction if total_conviction > 0 else 0.0
        
        await self._redis.hset(key, mapping={
            "count": str(count),
            "weighted_sum": str(weighted_sum),
            "total_conviction": str(total_conviction),
            "avg_sentiment": str(avg_sentiment),
        })
        await self._redis.expire(key, 86400 * 2)  # 2 days TTL

    async def _emit_complete_event(self, article_id: str, ticker: str, sentiment: float) -> None:
        """Emit sentiment complete event to Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        event = {
            "event_type": "analysis.sentiment.complete",
            "article_id": article_id,
            "ticker": ticker,
            "sentiment": sentiment,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self._redis.publish("analysis.sentiment.complete", str(event))

    async def analyze_article(
        self, article_id: str, tickers: list[str], summary_tr: str
    ) -> list[dict[str, Any]]:
        """
        Analyze sentiment for an article and tickers.
        
        Args:
            article_id: Unique article identifier
            tickers: List of tickers mentioned in article
            summary_tr: Turkish summary of article
            
        Returns:
            List of sentiment results per ticker
        """
        results = []
        
        for ticker in tickers:
            # Check idempotency
            idempotency_key = self._check_idempotency(f"{article_id}_{ticker}")
            if await self._is_duplicate(idempotency_key):
                logger.info("skipping_duplicate", article_id=article_id, ticker=ticker)
                continue
            
            # Simple rule-based sentiment (in production, would use LLM)
            sentiment, conviction = self._compute_sentiment(summary_tr)
            
            # Insert into database
            try:
                await self._insert_sentiment(article_id, ticker, sentiment, conviction)
            except Exception as e:
                logger.error("db_insert_failed", article_id=article_id, error=str(e))
            
            # Update daily aggregate
            try:
                await self._update_daily_aggregate(ticker, sentiment, conviction)
            except Exception as e:
                logger.error("redis_aggregate_failed", article_id=article_id, error=str(e))
            
            # Emit event
            try:
                await self._emit_complete_event(article_id, ticker, sentiment)
            except Exception as e:
                logger.error("redis_publish_failed", article_id=article_id, error=str(e))
            
            await self._mark_processed(idempotency_key)
            results.append({"ticker": ticker, "sentiment": sentiment, "conviction": conviction})
        
        return results

    def _compute_sentiment(self, text: str) -> tuple[float, float]:
        """Compute sentiment score from text (simplified rule-based)."""
        # Positive keywords
        positive = ["yükseliş", "artış", "pozitif", "büyüme", "rekor", "kazanç", "bullish", "beat"]
        negative = ["düşüş", "negatif", "kayıp", "zarar", "bearish", "miss", "risk", "kriz"]
        
        text_lower = text.lower()
        pos_count = sum(1 for p in positive if p in text_lower)
        neg_count = sum(1 for n in negative if n in text_lower)
        
        if pos_count > neg_count:
            sentiment = min(0.8, 0.3 + (pos_count - neg_count) * 0.15)
            conviction = min(0.9, 0.5 + (pos_count - neg_count) * 0.1)
        elif neg_count > pos_count:
            sentiment = max(-0.8, -0.3 - (neg_count - pos_count) * 0.15)
            conviction = min(0.9, 0.5 + (neg_count - pos_count) * 0.1)
        else:
            sentiment = 0.0
            conviction = 0.3
        
        return sentiment, conviction

    async def run(self) -> None:
        """Run the service (listen for Redis events)."""
        await self.initialize()
        logger.info("sentiment_analysis_service_started")
        
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        
        try:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe("analysis.news.complete")
            
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    if data.get("event_type") == "analysis.news.complete":
                        tickers = data.get("tickers", [])
                        if tickers:
                            await self.analyze_article(
                                article_id=data["article_id"],
                                tickers=tickers,
                                summary_tr=data.get("summary_tr", ""),
                            )
                except Exception as e:
                    logger.error("event_processing_error", error=str(e))
        finally:
            await self.close()
