"""FastAPI handlers for Decision Engine service."""
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from decision_engine.models import (
    Action,
    DecisionRecord,
    DecisionResponse,
    Evidence,
)
from decision_engine.service import DecisionEngineService

router = APIRouter(prefix="/decision", tags=["decision"])


class MakeDecisionRequest(BaseModel):
    """Request to make a trading decision."""

    portfolio_id: str = Field(..., description="Portfolio identifier")
    ticker: str = Field(..., description="Ticker symbol")
    evidence: list[Evidence] | None = Field(None, description="Optional explicit evidence")


class ComplianceReviewRequest(BaseModel):
    """Request to review/approve/block a decision."""

    decision_id: str
    approved: bool
    reason: str | None = None


class DecisionStatusResponse(BaseModel):
    """Response containing decision status."""

    decision_id: str
    portfolio_id: str
    ticker: str
    action: str
    confidence: float
    compliance_status: str
    created_at: str


# Service instance
_service: DecisionEngineService | None = None


def get_service() -> DecisionEngineService:
    """Get or create service instance."""
    global _service
    if _service is None:
        _service = DecisionEngineService()
    return _service


@router.post("/make", response_model=DecisionResponse)
async def make_decision(request: MakeDecisionRequest) -> DecisionResponse:
    """
    Make a trading decision for a ticker in a portfolio.

    This endpoint aggregates evidence from all analysis streams and produces
    a decision record with action, confidence, and position size.
    """
    service = get_service()

    try:
        decision, aggregated = await service.make_decision(
            portfolio_id=request.portfolio_id,
            ticker=request.ticker,
            evidence=request.evidence,
        )

        return DecisionResponse(decision=decision, aggregated_evidence=aggregated)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decision failed: {e!s}")


@router.get("/{decision_id}", response_model=DecisionRecord)
async def get_decision(decision_id: str) -> DecisionRecord:
    """Get a specific decision by ID."""
    service = get_service()

    try:
        async with service._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT decision_id, portfolio_id, ticker, action, confidence,
                       position_size_pct, evidence_count, contradiction_score,
                       supervisor_reasoning, compliance_status, effective_at,
                       created_at, data_completeness, disclaimer_tr, prompt_versions
                FROM decision.decisions
                WHERE decision_id = $1
                """,
                decision_id,
            )

            if row is None:
                raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")

            return DecisionRecord(
                decision_id=row["decision_id"],
                portfolio_id=row["portfolio_id"],
                ticker=row["ticker"],
                action=Action(row["action"]),
                confidence=row["confidence"],
                position_size_pct=row["position_size_pct"],
                evidence_count=row["evidence_count"],
                contradiction_score=row["contradiction_score"],
                supervisor_reasoning=row["supervisor_reasoning"] or "",
                compliance_status=row["compliance_status"],
                effective_at=row["effective_at"].isoformat() if row["effective_at"] else "",
                created_at=row["created_at"].isoformat() if row["created_at"] else "",
                data_completeness=row["data_completeness"],
                disclaimer_tr=row["disclaimer_tr"] or "",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch decision: {e!s}")


@router.get("/portfolio/{portfolio_id}/latest")
async def get_latest_decisions(portfolio_id: str) -> list[DecisionStatusResponse]:
    """Get latest decision for each ticker in a portfolio."""
    service = get_service()

    try:
        async with service._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (ticker)
                       decision_id, portfolio_id, ticker, action, confidence,
                       compliance_status, created_at
                FROM decision.decisions
                WHERE portfolio_id = $1
                ORDER BY ticker, created_at DESC
                """,
                portfolio_id,
            )

            return [
                DecisionStatusResponse(
                    decision_id=row["decision_id"],
                    portfolio_id=row["portfolio_id"],
                    ticker=row["ticker"],
                    action=row["action"],
                    confidence=row["confidence"],
                    compliance_status=row["compliance_status"],
                    created_at=row["created_at"].isoformat() if row["created_at"] else "",
                )
                for row in rows
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch decisions: {e!s}")


@router.post("/compliance/review")
async def review_decision(request: ComplianceReviewRequest) -> dict[str, Any]:
    """Review and approve/block a pending decision."""
    service = get_service()

    try:
        async with service._pool.acquire() as conn:
            new_status = "APPROVED" if request.approved else "BLOCKED"
            result = await conn.execute(
                """
                UPDATE decision.decisions
                SET compliance_status = $1, compliance_reason = $2
                WHERE decision_id = $3
                """,
                new_status,
                request.reason,
                request.decision_id,
            )

            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail=f"Decision {request.decision_id} not found")

            return {
                "decision_id": request.decision_id,
                "compliance_status": new_status,
                "reason": request.reason,
                "reviewed_at": datetime.now(UTC).isoformat(),
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to review decision: {e!s}")


@router.get("/ticker/{ticker}/history")
async def get_decision_history(
    ticker: str, portfolio_id: str | None = None, limit: int = 20
) -> list[DecisionStatusResponse]:
    """Get decision history for a ticker."""
    service = get_service()

    try:
        async with service._pool.acquire() as conn:
            if portfolio_id:
                rows = await conn.fetch(
                    """
                    SELECT decision_id, portfolio_id, ticker, action, confidence,
                           compliance_status, created_at
                    FROM decision.decisions
                    WHERE ticker = $1 AND portfolio_id = $2
                    ORDER BY created_at DESC
                    LIMIT $3
                    """,
                    ticker,
                    portfolio_id,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT decision_id, portfolio_id, ticker, action, confidence,
                           compliance_status, created_at
                    FROM decision.decisions
                    WHERE ticker = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    ticker,
                    limit,
                )

            return [
                DecisionStatusResponse(
                    decision_id=row["decision_id"],
                    portfolio_id=row["portfolio_id"],
                    ticker=row["ticker"],
                    action=row["action"],
                    confidence=row["confidence"],
                    compliance_status=row["compliance_status"],
                    created_at=row["created_at"].isoformat() if row["created_at"] else "",
                )
                for row in rows
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch decision history: {e!s}")


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "decision_engine"}
