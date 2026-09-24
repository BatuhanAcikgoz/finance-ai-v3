"""FastAPI handlers for Sector Analysis service."""
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sector_analysis.models import SectorScore
from sector_analysis.service import SectorAnalysisService

router = APIRouter(prefix="/sector", tags=["sector"])


class RunAnalysisRequest(BaseModel):
    """Request to run sector analysis."""

    is_weekly: bool = Field(False, description="Also compute correlation matrix")


class RunAnalysisResponse(BaseModel):
    """Response from sector analysis."""

    analysis_id: str
    analyzed_at: str
    sector_count: int
    data_completeness: str
    top_3: list[str]
    bottom_3: list[str]


# Service instance
_service: SectorAnalysisService | None = None


def get_service() -> SectorAnalysisService:
    """Get or create service instance."""
    global _service
    if _service is None:
        _service = SectorAnalysisService()
    return _service


@router.post("/analyze", response_model=RunAnalysisResponse)
async def run_analysis(request: RunAnalysisRequest) -> RunAnalysisResponse:
    """
    Run sector analysis for all BIST sectors.

    This endpoint triggers a full sector analysis including:
    - Period returns (1d, 1w, 1m, 3m, YTD)
    - Breadth metrics (% above SMA50/SMA200)
    - Relative strength vs BIST-100
    - Composite scoring and ranking

    If is_weekly=True, also computes the cross-sector correlation matrix.
    """
    service = get_service()

    try:
        result = await service.run_daily_analysis(is_weekly=request.is_weekly)

        return RunAnalysisResponse(
            analysis_id=result.analysis_id,
            analyzed_at=result.analyzed_at,
            sector_count=len(result.sector_scores),
            data_completeness=result.data_completeness,
            top_3=[s.ticker for s in result.sector_scores[:3]],
            bottom_3=[s.ticker for s in result.sector_scores[-3:]],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sector analysis failed: {e!s}")


@router.get("/scores", response_model=list[SectorScore])
async def get_sector_scores(date: str | None = None) -> list[SectorScore]:
    """
    Get sector scores for a specific date (defaults to today).

    Returns all 14 sectors ranked by composite score.
    """
    service = get_service()
    target_date = date or datetime.now(UTC).date().isoformat()

    try:
        async with service._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT analysis_id, ticker, total_score, momentum_score,
                       breadth_score, rs_score, rank, signal, analyzed_at
                FROM analysis.sector_analyses
                WHERE analyzed_at::date = $1
                ORDER BY rank ASC
                """,
                target_date,
            )

            return [
                SectorScore(
                    ticker=row["ticker"],
                    total_score=row["total_score"],
                    momentum_score=row["momentum_score"],
                    breadth_score=row["breadth_score"],
                    relative_strength_score=row["rs_score"],
                    rank=row["rank"],
                    signal=row["signal"],
                )
                for row in rows
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sector scores: {e!s}")


@router.get("/rank/{ticker}")
async def get_sector_rank(ticker: str) -> dict[str, Any]:
    """Get rank and score for a specific sector."""
    service = get_service()

    try:
        async with service._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ticker, total_score, rank, signal, analyzed_at
                FROM analysis.sector_analyses
                WHERE ticker = $1
                ORDER BY analyzed_at DESC
                LIMIT 1
                """,
                ticker,
            )

            if row is None:
                raise HTTPException(status_code=404, detail=f"Sector {ticker} not found")

            return {
                "ticker": row["ticker"],
                "total_score": row["total_score"],
                "rank": row["rank"],
                "signal": row["signal"],
                "analyzed_at": row["analyzed_at"].isoformat() if row["analyzed_at"] else None,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sector rank: {e!s}")


@router.get("/correlation")
async def get_correlation_matrix(date: str | None = None) -> dict[str, Any]:
    """Get the latest cross-sector correlation matrix."""
    service = get_service()
    target_date = date or datetime.now(UTC).date().isoformat()

    try:
        async with service._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT tickers, correlation_matrix, computed_at
                FROM analysis.sector_correlations
                WHERE computed_at::date <= $1
                ORDER BY computed_at DESC
                LIMIT 1
                """,
                target_date,
            )

            if row is None:
                return {"error": "No correlation matrix found"}

            return {
                "tickers": row["tickers"],
                "correlation_matrix": row["correlation_matrix"],
                "computed_at": row["computed_at"].isoformat() if row["computed_at"] else None,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch correlation matrix: {e!s}")


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "sector_analysis"}
