"""Decision endpoints — backed by ``decision.decisions`` Postgres table.

Endpoints:
  GET  /v1/decisions/recent           → list recent decisions
  GET  /v1/decisions/{decision_id}    → fetch by UUID
  POST /v1/decisions/synthesize       → insert (used by decision-engine worker)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

import db

logger = logging.getLogger(__name__)
router = APIRouter()


# -- request/response models ------------------------------------------------

class SynthesizeRequest(BaseModel):
    """Payload from the decision-engine worker.

    Only the minimum required to satisfy ``decision.decisions`` NOT NULL
    columns; everything else falls back to a sane default.
    """
    symbol: str = Field(..., min_length=1, max_length=5,
                        description="Ticker symbol (e.g. THYAO)")
    score: float = Field(..., ge=0.0, le=1.0,
                         description="Decision confidence 0..1")
    rationale: str = Field(..., min_length=1,
                           description="Supervisor reasoning / evidence summary")
    action: str = Field("BUY",
                        description="BUY | SELL | HOLD | REDUCE | INSUFFICIENT_EVIDENCE")
    portfolio_id: Optional[str] = Field(
        None, description="Portfolio UUID; auto-generated if omitted (dev mode)")
    position_size_pct: Optional[float] = Field(None, ge=0.0, le=0.25)
    evidence: Optional[dict] = Field(default_factory=dict)
    evidence_count: Optional[int] = Field(0, ge=0)
    contradiction_score: Optional[float] = Field(0.0, ge=0.0, le=1.0)
    compliance_status: str = Field("PENDING",
                                   description="PENDING | APPROVED | BLOCKED")
    data_completeness: str = Field("PARTIAL")
    prompt_versions: Optional[dict] = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def _upper_symbol(cls, v: str) -> str:
        return v.upper()

    @field_validator("action")
    @classmethod
    def _valid_action(cls, v: str) -> str:
        v = v.upper()
        if v not in {"BUY", "SELL", "HOLD", "REDUCE", "INSUFFICIENT_EVIDENCE"}:
            raise ValueError(f"invalid action: {v}")
        return v


class SynthesizeResponse(BaseModel):
    decision_id: str
    created_at: str
    status: str = "stored"


def _row_to_dict(row) -> dict:
    return {
        "decision_id": str(row["decision_id"]),
        "portfolio_id": str(row["portfolio_id"]),
        "ticker": row["ticker"],
        "action": row["action"],
        "confidence": float(row["confidence"]) if row["confidence"] is not None else None,
        "position_size_pct": float(row["position_size_pct"]) if row["position_size_pct"] is not None else None,
        "evidence": row["evidence"],
        "evidence_count": row["evidence_count"],
        "contradiction_score": float(row["contradiction_score"]) if row["contradiction_score"] is not None else None,
        "supervisor_reasoning": row["supervisor_reasoning"],
        "portfolio_context": row["portfolio_context"],
        "compliance_status": row["compliance_status"],
        "compliance_reason": row["compliance_reason"],
        "effective_at": row["effective_at"].isoformat() if row["effective_at"] else None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "data_completeness": row["data_completeness"],
        "prompt_versions": row["prompt_versions"],
    }


# -- endpoints --------------------------------------------------------------

@router.get("/recent")
async def list_recent_decisions(
    ticker: Optional[str] = Query(None, description="filter by ticker"),
    portfolio_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    compliance_status: Optional[str] = Query(None),
):
    """Recent decisions, optionally filtered."""
    where = []
    args: list = []
    if ticker:
        where.append(f"ticker = ${len(args)+1}")
        args.append(ticker.upper())
    if portfolio_id:
        where.append(f"portfolio_id = ${len(args)+1}")
        try:
            args.append(uuid.UUID(portfolio_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="portfolio_id must be a UUID")
    if compliance_status:
        where.append(f"compliance_status = ${len(args)+1}")
        args.append(compliance_status.upper())
    where_clause = ("WHERE " + " AND ".join(where)) if where else ""
    args.append(limit)
    limit_clause = f"${len(args)}"

    rows = await db.fetch(
        f"""
        SELECT decision_id, portfolio_id, ticker, action, confidence,
               position_size_pct, evidence, evidence_count, contradiction_score,
               supervisor_reasoning, portfolio_context, compliance_status,
               compliance_reason, effective_at, created_at, data_completeness,
               prompt_versions
        FROM decision.decisions
        {where_clause}
        ORDER BY created_at DESC
        LIMIT {limit_clause}
        """,
        *args,
    )
    if not rows and not await db.is_available():
        return {"items": [], "count": 0, "degraded": True}
    items = [_row_to_dict(r) for r in rows]
    return {"items": items, "count": len(items)}


@router.get("/{decision_id}")
async def get_decision(decision_id: str):
    """Fetch decision by UUID."""
    try:
        did = uuid.UUID(decision_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="decision_id must be a UUID")

    row = await db.fetchrow(
        """
        SELECT decision_id, portfolio_id, ticker, action, confidence,
               position_size_pct, evidence, evidence_count, contradiction_score,
               supervisor_reasoning, portfolio_context, compliance_status,
               compliance_reason, effective_at, created_at, data_completeness,
               prompt_versions
        FROM decision.decisions
        WHERE decision_id = $1
        """,
        did,
    )
    if row is None:
        if not await db.is_available():
            raise HTTPException(status_code=503, detail="postgres unavailable")
        raise HTTPException(status_code=404, detail="decision not found")
    return _row_to_dict(row)


@router.post("/synthesize", response_model=SynthesizeResponse, status_code=201)
async def synthesize_decision(req: SynthesizeRequest):
    """Insert a new decision row.

    Used by ``services/decision_engine`` workers. Returns the generated
    ``decision_id`` so the caller can publish it to message buses downstream.
    """
    # Generate portfolio_id if the worker didn't supply one (dev convenience).
    portfolio_uuid = (
        uuid.UUID(req.portfolio_id) if req.portfolio_id else uuid.uuid4()
    )
    new_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    status_msg = await db.execute(
        """
        INSERT INTO decision.decisions (
            decision_id, portfolio_id, ticker, action, confidence,
            position_size_pct, evidence, evidence_count, contradiction_score,
            supervisor_reasoning, compliance_status, effective_at,
            data_completeness, prompt_versions
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7::jsonb, $8, $9,
            $10, $11, $12,
            $13, $14::jsonb
        )
        """,
        new_id, portfolio_uuid, req.symbol, req.action, req.score,
        req.position_size_pct,
        _json(req.evidence or {}),
        req.evidence_count or 0,
        req.contradiction_score or 0.0,
        req.rationale,
        req.compliance_status.upper(),
        now,
        req.data_completeness,
        _json(req.prompt_versions or {}),
    )
    if not status_msg:
        # db.execute returns "" when pool unavailable.
        if not await db.is_available():
            raise HTTPException(status_code=503, detail="postgres unavailable")
        raise HTTPException(status_code=500, detail="insert failed")

    return SynthesizeResponse(
        decision_id=str(new_id),
        created_at=now.isoformat(),
        status="stored",
    )


# -- helpers ----------------------------------------------------------------

def _json(value) -> str:
    """Asyncpg wants jsonb as a JSON string, not a Python dict."""
    import json
    return json.dumps(value, default=str)