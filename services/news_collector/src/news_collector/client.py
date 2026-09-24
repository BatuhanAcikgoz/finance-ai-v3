"""News API and RSS client for fetching articles."""
from typing import Any

import feedparser
import httpx
from bs4 import BeautifulSoup


class RSSClient:
    """Client for fetching and parsing RSS feeds."""

    def __init__(self) -> None:
        """Initialize RSS client."""
        self._client = httpx.AsyncClient(timeout=30.0)

    async def fetch_feed(self, url: str) -> list[dict[str, Any]]:
        """
        Fetch and parse an RSS feed.

        Args:
            url: RSS feed URL

        Returns:
            List of feed entries
        """
        response = await self._client.get(url)
        response.raise_for_status()

        feed = feedparser.parse(response.content)
        entries = []

        for entry in feed.entries:
            entries.append({
                "guid": entry.get("id", ""),
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", ""),
                "author": entry.get("author", ""),
            })

        return entries

    async def scrape_article(self, url: str, source: str) -> dict[str, Any]:
        """
        Scrape full article body from URL.

        Args:
            url: Article URL
            source: News source identifier

        Returns:
            Article body and metadata
        """
        response = await self._client.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; FinanceAI/1.0; +https://example.com)",
            },
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "lxml")

        # Source-specific selectors
        selectors = {
            "BLOOMBERG_HT": "div.content__article-body",
            "AA": "div.detailed-content",
            "REUTERS": "div.article-body",
            "DUNYA": "div.news-detail",
            "CAPITAL": "div.article-content",
        }

        selector = selectors.get(source, "article")
        article_div = soup.select_one(selector)

        if article_div:
            body = article_div.get_text(separator="\n", strip=True)
        else:
            # Fallback to all paragraph text
            paragraphs = soup.find_all("p")
            body = "\n".join(p.get_text(strip=True) for p in paragraphs)

        # Extract publish time
        time_elem = soup.find("time")
        published_at = time_elem.get("datetime") if time_elem else None

        return {
            "body": body[:50000] if body else None,  # Limit to 50k chars
            "published_at": published_at,
        }

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()


class NewsAPIClient:
    """Client for news API (alternative to RSS)."""

    def __init__(self) -> None:
        """Initialize news API client."""
        self._client = httpx.AsyncClient(timeout=30.0)

    async def get_articles(
        self, source: str, since: str | None = None, max_results: int = 50
    ) -> list[dict[str, Any]]:
        """
        Fetch articles from news API.

        Args:
            source: News source identifier
            since: ISO timestamp to fetch articles since
            max_results: Maximum number of results

        Returns:
            List of article records
        """
        # Placeholder - in production, this would call actual news APIs
        return []

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
