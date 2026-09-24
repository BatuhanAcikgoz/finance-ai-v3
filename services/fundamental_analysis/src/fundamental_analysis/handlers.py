"""FastAPI handlers for Fundamental Analysis service."""
from typing import Any

from pydantic import BaseModel

from fundamental_analysis.service import FundamentalAnalysisService


class AnalyzeKAPRequest(BaseModel):
    """Request body for analyze_kap endpoint."""

    publishing_id: str
    title: str
    category: str
    tickers: list[str]


class AnalyzeKAPResponse(BaseModel):
    """Response from analyze_kap endpoint."""

    analysis_id: str
    ticker: str
    direction: str
    strength: float
    confidence: float
    data_completeness: str
    peer_count: int
    reasoning: str


_service: FundamentalAnalysisService | None = None


def get_service() -> FundamentalAnalysisService:
    """Get or create the service instance."""
    global _service
    if _service is None:
        _service = FundamentalAnalysisService()
    return _service


async def analyze_kap_handler(
    request: AnalyzeKAPRequest,
) -> dict[str, Any]:
    """
    Analyze a KAP disclosure and return fundamental analysis result.

    This endpoint is typically triggered by webhooks from the KAP collector
    or by the scheduler.
    """
    service = get_service()
    await service.initialize()

    try:
        result = await service.analyze_kap(
            publishing_id=request.publishing_id,
            title=request.title,
            category=request.category,
            tickers=request.tickers,
        )

        if result is None:
            return {
                "status": "skipped",
                "publishing_id": request.publishing_id,
                "message": "Analysis was skipped (duplicate or no financials)",
            }

        return {
            "status": "success",
            "analysis_id": result.analysis_timestamp.isoformat() + "_" + result.ticker,
            "ticker": result.ticker,
            "direction": result.direction.value,
            "strength": result.strength,
            "confidence": result.confidence,
            "data_completeness": result.data_completeness.value,
            "peer_count": result.peer_count,
            "reasoning": result.reasoning,
            "ratios": result.ratios.model_dump(),
            "peer_percentiles": (
                result.peer_percentiles.model_dump() if result.peer_percentiles else None
            ),
        }
    finally:
        await service.close()


async def health_check_handler() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "fundamental_analysis"}
