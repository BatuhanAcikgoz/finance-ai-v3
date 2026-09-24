"""FastAPI handlers for Macro Analysis service."""
from typing import Any

from pydantic import BaseModel

from macro_analysis.service import MacroAnalysisService


class AnalyzeMacroRequest(BaseModel):
    """Request body for analyze_macro endpoint."""

    indicator_code: str
    source: str
    value: float
    unit: str
    release_date: str


class AnalyzeMacroResponse(BaseModel):
    """Response from analyze_macro endpoint."""

    analysis_id: str
    indicator_code: str
    source: str
    regime: str
    confidence: float
    reasoning: str


_service: MacroAnalysisService | None = None


def get_service() -> MacroAnalysisService:
    """Get or create the service instance."""
    global _service
    if _service is None:
        _service = MacroAnalysisService()
    return _service


async def analyze_macro_handler(
    request: AnalyzeMacroRequest,
) -> dict[str, Any]:
    """
    Analyze a macro indicator release.

    This endpoint is typically triggered by webhooks from the macro_collector.
    """
    service = get_service()
    await service.initialize()

    try:
        result = await service.analyze_macro(
            indicator_code=request.indicator_code,
            source=request.source,
            value=request.value,
            unit=request.unit,
            release_date=request.release_date,
        )

        if result is None:
            return {
                "status": "skipped",
                "indicator_code": request.indicator_code,
                "message": "Analysis was skipped (duplicate)",
            }

        return {
            "status": "success",
            "analysis_id": result.analysis_timestamp.isoformat() + "_" + result.indicator_code,
            "indicator_code": result.indicator_code,
            "source": result.source.value,
            "regime": result.regime.value,
            "regime_changed": result.regime_changed,
            "confidence": result.confidence,
            "impact_estimates": result.impact_estimates.model_dump(),
            "reasoning": result.reasoning,
        }
    finally:
        await service.close()


async def health_check_handler() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "macro_analysis"}
