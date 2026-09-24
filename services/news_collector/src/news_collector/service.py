"""News Collector main service logic."""
import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from redis.asyncio import Redis

from news_collector.client import RSSClient
from news_collector.config import settings

logger = structlog.get_logger(__name__)


class NewsCollectorService:
    """Service for collecting and processing news articles."""

    # RSS feed URLs for Turkish financial news sources
    RSS_FEEDS: dict[str, str] = {
        "BLOOMBERG_HT": "https://www.bloomberght.com/rss",
        "AA": "https://www.aa.com.tr/rss/rssNews?channel=economy",
        "FOREX": "https://www.foreks.com/rss/haberler",
        "DUNYA": "https://www.dunya.com/rss",
        "EKONOMIM": "https://www.ekonomim.com/rss",
        "BIGPARA": "https://bigpara.hurriyet.com.tr/rss/",
    }

    def __init__(self) -> None:
        """Initialize news collector service."""
        self._rss_client = RSSClient()
        self._redis: Redis | None = None

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        self._redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

    async def close(self) -> None:
        """Close all connections."""
        if self._redis:
            await self._redis.close()
        await self._rss_client.close()

    def _compute_content_hash(self, content: str) -> str:
        """Compute SHA-256 hash for deduplication."""
        normalized = " ".join(content.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()

    async def _is_duplicate(self, content_hash: str) -> bool:
        """Check if this article was already processed."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        return bool(await self._redis.exists(f"news:hash:{content_hash}"))

    async def _mark_processed(self, content_hash: str) -> None:
        """Mark article as processed in Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        await self._redis.setex(
            f"news:hash:{content_hash}",
            settings.dedup_ttl_days * 86400,
            "1",
        )

    async def poll_sources(self) -> tuple[int, int, int]:
        """
        Poll all configured news sources.

        Returns:
            Tuple of (total_processed, new_inserted, duplicates_skipped)
        """
        total_processed = 0
        new_inserted = 0
        duplicates_skipped = 0

        for source, feed_url in self.RSS_FEEDS.items():
            try:
                processed, inserted, dupes = await self._poll_single_source(source, feed_url)
                total_processed += processed
                new_inserted += inserted
                duplicates_skipped += dupes
            except Exception as e:
                logger.error(
                    "news_source_error",
                    source=source,
                    feed_url=feed_url,
                    error=str(e),
                )

        logger.info(
            "news_poll_completed",
            total_processed=total_processed,
            new_inserted=new_inserted,
            duplicates_skipped=duplicates_skipped,
        )

        return total_processed, new_inserted, duplicates_skipped

    async def _poll_single_source(
        self, source: str, feed_url: str
    ) -> tuple[int, int, int]:
        """Poll a single news source."""
        entries = await self._rss_client.fetch_feed(feed_url)

        total_processed = 0
        new_inserted = 0
        duplicates_skipped = 0

        for entry in entries:
            total_processed += 1

            # Compute content hash for deduplication
            content = f"{entry.get('title', '')} {entry.get('summary', '')}"
            content_hash = self._compute_content_hash(content)

            # Check for duplicate
            if await self._is_duplicate(content_hash):
                duplicates_skipped += 1
                continue

            # Scrape full article body
            article_data = {
                "article_id": str(uuid.uuid4()),
                "source": source,
                "url": entry.get("link", ""),
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "author": entry.get("author"),
                "published_at": entry.get("published", ""),
                "content_hash": content_hash,
                "body": None,
                "needs_rescrape": False,
            }

            # Try to scrape full article
            try:
                scraped = await self._rss_client.scrape_article(entry.get("link", ""), source)
                article_data["body"] = scraped.get("body")
                if not article_data["body"]:
                    article_data["needs_rescrape"] = True
            except Exception as e:
                logger.warning(
                    "article_scrape_failed",
                    url=entry.get("link", ""),
                    error=str(e),
                )
                article_data["needs_rescrape"] = True

            # Insert into database
            await self._insert_article(article_data)
            new_inserted += 1

            # Mark as processed
            await self._mark_processed(content_hash)

            # Emit event to Redis
            await self._emit_news_event(article_data)

        return total_processed, new_inserted, duplicates_skipped

    async def _insert_article(self, article: dict[str, Any]) -> None:
        """Insert article into PostgreSQL."""
        import asyncpg

        pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO news.articles (
                        article_id, source, url, title, summary, body,
                        author, published_at, ingested_at, language,
                        content_hash, needs_rescrape
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (content_hash) DO NOTHING
                    """,
                    article["article_id"],
                    article["source"],
                    article["url"],
                    article["title"],
                    article["summary"],
                    article["body"],
                    article["author"],
                    article["published_at"],
                    datetime.now(UTC).isoformat(),
                    "tr",
                    article["content_hash"],
                    article["needs_rescrape"],
                )
        finally:
            await pool.close()

    async def _emit_news_event(self, article: dict[str, Any]) -> None:
        """Emit new article event to Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")

        event = {
            "event_type": "raw.news.new",
            "article_id": article["article_id"],
            "source": article["source"],
            "title": article["title"],
            "url": article["url"],
            "tickers": [],  # Ticker extraction would be done by news_analysis
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self._redis.publish("raw.news.new", str(event))

    async def run(self) -> None:
        """Run the collector (continuous polling)."""
        await self.initialize()
        logger.info("news_collector_started", poll_interval=settings.poll_interval_seconds)

        try:
            while True:
                try:
                    await self.poll_sources()
                except Exception as e:
                    logger.error("news_poll_error", error=str(e))

                import asyncio
                await asyncio.sleep(settings.poll_interval_seconds)
        finally:
            await self.close()
