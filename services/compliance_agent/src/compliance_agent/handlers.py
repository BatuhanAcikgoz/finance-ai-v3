"""FastAPI handlers for Compliance Agent service."""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from compliance_agent.models import ComplianceStatus, DecisionForReview
from compliance_agent.service import ComplianceAgentService

router = APIRouter(prefix="/compliance", tags=["compliance"])


class ReviewDecisionRequest(BaseModel):
    """Request to review a decision."""

    decision_id: str
    portfolio_id: str
    ticker: str
    action: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    position_size_pct: float = Field(..., ge=0.0, le=1.0)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    supervisor_reasoning: str
    data_completeness: str
    disclaimer_tr: str


class ReviewDecisionResponse(BaseModel):
    """Response from compliance review."""

    check_id: str
    decision_id: str
    status: ComplianceStatus
    violations: list[dict[str, Any]]
    checked_at: str


# Service instance
_service: ComplianceAgentService | None = None


def get_service() -> ComplianceAgentService:
    """Get or create service instance."""
    global _service
    if _service is None:
        _service = ComplianceAgentService()
    return _service


@router.post("/review", response_model=ReviewDecisionResponse)
async def review_decision(request: ReviewDecisionRequest) -> ReviewDecisionResponse:
    """
    Submit a decision for compliance review.

    The compliance agent checks:
    - No forbidden language (guaranteed returns, etc.)
    - Disclaimer is present
    - All evidence has source citations
    - Confidence is in valid range [0, 1]
    - Position size within constraints
    """
    service = get_service()

    decision = DecisionForReview(
        decision_id=request.decision_id,
        portfolio_id=request.portfolio_id,
        ticker=request.ticker,
        action=request.action,
        confidence=request.confidence,
        position_size_pct=request.position_size_pct,
        evidence=request.evidence,
        supervisor_reasoning=request.supervisor_reasoning,
        data_completeness=request.data_completeness,
        disclaimer_tr=request.disclaimer_tr,
    )

    try:
        result = await service.review_decision(decision)
        return ReviewDecisionResponse(
            check_id=result.check_id,
            decision_id=result.decision_id,
            status=result.status,
            violations=[v.model_dump() for v in result.violations],
            checked_at=result.checked_at,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compliance review failed: {e!s}")


@router.get("/audit/{decision_id}")
async def get_compliance_audit(decision_id: str) -> dict[str, Any]:
    """Get compliance audit record for a decision."""
    service = get_service()

    try:
        async with service._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT audit_id, check_id, decision_id, portfolio_id, ticker, action,
                       original_confidence, position_size_pct, status, violations,
                       reviewer_id, reviewed_at, notes
                FROM audit.compliance_audits
                WHERE decision_id = $1
                ORDER BY checked_at DESC
                LIMIT 1
                """,
                decision_id,
            )

            if row is None:
                raise HTTPException(status_code=404, detail=f"No audit record for decision {decision_id}")

            return {
                "audit_id": row["audit_id"],
                "check_id": row["check_id"],
                "decision_id": row["decision_id"],
                "portfolio_id": row["portfolio_id"],
                "ticker": row["ticker"],
                "action": row["action"],
                "original_confidence": row["original_confidence"],
                "position_size_pct": row["position_size_pct"],
                "status": row["status"],
                "violations": row["violations"],
                "reviewer_id": row["reviewer_id"],
                "reviewed_at": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
                "notes": row["notes"],
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch audit record: {e!s}")


@router.get("/blocked/recent")
async def get_recent_blocked(limit: int = 20) -> list[dict[str, Any]]:
    """Get recently blocked decisions."""
    service = get_service()

    try:
        async with service._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT audit_id, check_id, decision_id, portfolio_id, ticker,
                       original_confidence, violations, reviewed_at
                FROM audit.compliance_audits
                WHERE status = 'BLOCKED'
                ORDER BY reviewed_at DESC
                LIMIT $1
                """,
                limit,
            )

            return [
                {
                    "audit_id": row["audit_id"],
                    "check_id": row["check_id"],
                    "decision_id": row["decision_id"],
                    "portfolio_id": row["portfolio_id"],
                    "ticker": row["ticker"],
                    "confidence": row["original_confidence"],
                    "violations": row["violations"],
                    "blocked_at": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
                }
                for row in rows
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch blocked decisions: {e!s}")


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "compliance_agent"}
