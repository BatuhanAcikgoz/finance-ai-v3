"""FastAPI handlers for Sentiment Analysis service."""
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sentiment_analysis.service import SentimentAnalysisService

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


class AnalyzeArticleRequest(BaseModel):
    """Request to analyze article sentiment."""

    article_id: str = Field(..., description="Unique article identifier")
    tickers: list[str] = Field(..., description="List of tickers mentioned in article")
    summary_tr: str = Field(..., description="Turkish summary of article")


class SentimentResult(BaseModel):
    """Sentiment analysis result for a single ticker."""

    ticker: str
    sentiment: float = Field(..., ge=-1.0, le=1.0, description="Sentiment score -1 to +1")
    conviction: float = Field(..., ge=0.0, le=1.0, description="Confidence in sentiment")


class AnalyzeArticleResponse(BaseModel):
    """Response from sentiment analysis."""

    article_id: str
    results: list[SentimentResult]
    processed_at: str


# Service instance (initialized on startup)
_service: SentimentAnalysisService | None = None


def get_service() -> SentimentAnalysisService:
    """Get or create service instance."""
    global _service
    if _service is None:
        _service = SentimentAnalysisService()
    return _service


@router.post("/analyze", response_model=AnalyzeArticleResponse)
async def analyze_article(request: AnalyzeArticleRequest) -> AnalyzeArticleResponse:
    """
    Analyze sentiment for an article and its associated tickers.

    This endpoint processes a news article and returns sentiment scores
    for each ticker mentioned. Sentiment ranges from -1 (bearish) to +1 (bullish).
    """
    service = get_service()

    try:
        results = await service.analyze_article(
            article_id=request.article_id,
            tickers=request.tickers,
            summary_tr=request.summary_tr,
        )

        return AnalyzeArticleResponse(
            article_id=request.article_id,
            results=[SentimentResult(**r) for r in results],
            processed_at=datetime.now(UTC).isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sentiment analysis failed: {e!s}")


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "sentiment_analysis"}


@router.get("/ticker/{ticker}/daily")
async def get_daily_sentiment(ticker: str) -> dict[str, Any]:
    """
    Get aggregated daily sentiment for a ticker.

    Returns the conviction-weighted average sentiment for today.
    """
    service = get_service()

    try:
        async with service._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    ticker,
                    DATE(analyzed_at) as date,
                    COUNT(*) as article_count,
                    AVG(sentiment * conviction) / NULLIF(AVG(conviction), 0) as weighted_sentiment,
                    AVG(conviction) as avg_conviction
                FROM analysis.sentiment_analyses
                WHERE ticker = $1 AND analyzed_at >= CURRENT_DATE
                GROUP BY ticker, DATE(analyzed_at)
                """,
                ticker,
            )

            if row is None:
                return {
                    "ticker": ticker,
                    "date": datetime.now(UTC).date().isoformat(),
                    "article_count": 0,
                    "weighted_sentiment": None,
                    "avg_conviction": None,
                }

            return {
                "ticker": row["ticker"],
                "date": row["date"].isoformat(),
                "article_count": row["article_count"],
                "weighted_sentiment": float(row["weighted_sentiment"]) if row["weighted_sentiment"] else None,
                "avg_conviction": float(row["avg_conviction"]) if row["avg_conviction"] else None,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch daily sentiment: {e!s}")
