"""FastAPI handlers for News Analysis service."""
from typing import Any

from pydantic import BaseModel

from news_analysis.service import NewsAnalysisService


class AnalyzeNewsRequest(BaseModel):
    """Request body for analyze_news endpoint."""

    article_id: str
    title: str
    body: str
    source: str


class AnalyzeNewsResponse(BaseModel):
    """Response from analyze_news endpoint."""

    analysis_id: str
    article_id: str
    tickers: list[str]
    topic: str
    materiality: str


_service: NewsAnalysisService | None = None


def get_service() -> NewsAnalysisService:
    """Get or create the service instance."""
    global _service
    if _service is None:
        _service = NewsAnalysisService()
    return _service


async def analyze_news_handler(
    request: AnalyzeNewsRequest,
) -> dict[str, Any]:
    """
    Analyze a news article.

    This endpoint is typically triggered by webhooks from the news_collector.
    """
    service = get_service()
    await service.initialize()

    try:
        result = await service.analyze_article(
            article_id=request.article_id,
            title=request.title,
            body=request.body,
            source=request.source,
        )

        if result is None:
            return {
                "status": "skipped",
                "article_id": request.article_id,
                "message": "Analysis was skipped (duplicate)",
            }

        return {
            "status": "success",
            "analysis_id": result.analysis_timestamp.isoformat() + "_" + result.article_id,
            "article_id": result.article_id,
            "tickers": result.tickers,
            "topic": result.topic.value,
            "materiality": result.materiality.value,
            "summary_tr": result.summary_tr,
            "key_entities": result.key_entities,
            "confidence": result.confidence,
        }
    finally:
        await service.close()


async def health_check_handler() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "news_analysis"}
