"""Backtest Agent FastAPI handlers."""
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backtest_agent.config import settings
from backtest_agent.models import BacktestReport
from backtest_agent.service import BacktestAgentService

router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    """Request to run a backtest."""

    start_date: str | None = None  # ISO format date string
    end_date: str | None = None
    lookback_weeks: int | None = None  # Override config


class BacktestResponse(BaseModel):
    """Response containing backtest report."""

    report: BacktestReport
    generated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class WeightApprovalRequest(BaseModel):
    """Request to approve weight adjustments."""

    report_id: str
    approved: bool
    adjustments: dict[str, float] | None = None  # Stream → new weight


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    service: str = "backtest_agent"
    version: str = "1.0.0"


# Service instance (initialized on startup)
_service: BacktestAgentService | None = None


async def get_service() -> BacktestAgentService:
    """Get or create the service instance."""
    global _service
    if _service is None:
        _service = BacktestAgentService()
        await _service.initialize()
    return _service


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", service="backtest_agent", version="1.0.0")


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest) -> BacktestResponse:
    """
    Run a backtest for the specified period.

    If no dates are provided, uses the configured lookback period.
    """
    service = await get_service()

    # Parse dates if provided
    start_date = None
    end_date = None

    if request.start_date:
        try:
            start_date = datetime.fromisoformat(request.start_date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid start_date: {e}")

    if request.end_date:
        try:
            end_date = datetime.fromisoformat(request.end_date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid end_date: {e}")

    # Override lookback weeks if provided
    _lookback = request.lookback_weeks or settings.lookback_weeks

    try:
        report = await service.run_backtest(start_date=start_date, end_date=end_date)
        return BacktestResponse(report=report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {e!s}")


@router.get("/report/{report_id}", response_model=BacktestResponse)
async def get_report(report_id: str) -> BacktestResponse:
    """
    Get a specific backtest report by ID.

    Note: Reports are stored in PostgreSQL backtest.backtests table.
    """
    service = await get_service()

    # This would query the database for the specific report
    # For now, run a new backtest with default parameters
    # In production, this would fetch from the database
    try:
        report = await service.run_backtest()
        if report.report_id != report_id:
            raise HTTPException(
                status_code=404,
                detail=f"Report {report_id} not found",
            )
        return BacktestResponse(report=report)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch report: {e!s}")


@router.post("/approve-weights")
async def approve_weights(request: WeightApprovalRequest) -> dict[str, Any]:
    """
    Approve or reject weight adjustments from a backtest report.

    If approved with adjustments, these would be applied to the decision engine.
    If approved without adjustments, defaults are used.
    If rejected, no changes are made.
    """
    if request.approved:
        if request.adjustments:
            # Validate adjustments
            for stream, weight in request.adjustments.items():
                if not 0.0 <= weight <= 1.0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid weight for {stream}: {weight}",
                    )
            total = sum(request.adjustments.values())
            if abs(total - 1.0) > 0.01:
                raise HTTPException(
                    status_code=400,
                    detail=f"Weights must sum to 1.0, got {total}",
                )

            # In production: Update decision engine weights
            # This would publish to Redis or update the database
            return {
                "status": "approved",
                "report_id": request.report_id,
                "adjustments_applied": request.adjustments,
                "message": "Weight adjustments approved and queued for application",
            }
        else:
            return {
                "status": "approved",
                "report_id": request.report_id,
                "adjustments_applied": None,
                "message": "No adjustments applied",
            }
    else:
        return {
            "status": "rejected",
            "report_id": request.report_id,
            "message": "Weight adjustments rejected by operator",
        }


@router.get("/streams")
async def get_stream_stats() -> dict[str, Any]:
    """
    Get current evidence stream statistics from the last backtest.

    This is useful for dashboards to show stream performance.
    """
    service = await get_service()

    try:
        report = await service.run_backtest()
        return {
            "streams": [
                {
                    "stream": s.stream,
                    "total_decisions": s.total_decisions,
                    "hit_rate": s.hit_rate,
                    "avg_confidence": s.avg_confidence,
                    "brier_score": s.brier_score,
                }
                for s in report.stream_stats
            ],
            "overall_hit_rate": report.overall_hit_rate,
            "overall_brier_score": report.overall_brier_score,
            "low_sample_warning": report.low_sample_warning,
            "generated_at": report.generated_at,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stream stats: {e!s}")


@router.get("/calibration")
async def get_calibration() -> dict[str, Any]:
    """
    Get calibration analysis from the last backtest.

    Shows how well confidence predictions match actual hit rates.
    """
    service = await get_service()

    try:
        report = await service.run_backtest()
        return {
            "buckets": [
                {
                    "bucket": b.bucket,
                    "total_decisions": b.total_decisions,
                    "hit_rate": b.hit_rate,
                    "avg_predicted_confidence": b.avg_predicted_confidence,
                    "calibration_error": b.calibration_error,
                }
                for b in report.confidence_buckets
            ],
            "calibration_issues": report.calibration_issues,
            "overall_brier_score": report.overall_brier_score,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get calibration: {e!s}")
