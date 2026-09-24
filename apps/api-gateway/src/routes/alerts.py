"""Alerts endpoint — surfaces recent decisions as alerts.

Real implementation: queries ``decision.decisions`` for recent rows whose
``compliance_status`` is APPROVED or whose action is non-HOLD.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

import db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def list_alerts(
    ticker: Optional[str] = Query(None),
    grade: Optional[str] = Query(None,
        description="Filter by compliance grade (APPROVED|PENDING|BLOCKED)"),
    limit: int = Query(50, le=200),
):
    """Return recent actionable decisions as alerts."""
    where = ["action IN ('BUY','SELL','REDUCE')"]
    args: list = []
    if ticker:
        where.append(f"ticker = ${len(args)+1}")
        args.append(ticker.upper())
    if grade:
        where.append(f"compliance_status = ${len(args)+1}")
        args.append(grade.upper())
    args.append(limit)
    limit_clause = f"${len(args)}"

    rows = await db.fetch(
        f"""
        SELECT decision_id, portfolio_id, ticker, action, confidence,
               supervisor_reasoning, compliance_status, created_at
        FROM decision.decisions
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC
        LIMIT {limit_clause}
        """,
        *args,
    )
    if not rows and not await db.is_available():
        return {"items": [], "count": 0, "degraded": True}

    items = [
        {
            "alert_id": str(r["decision_id"]),
            "ticker": r["ticker"],
            "action": r["action"],
            "confidence": float(r["confidence"]) if r["confidence"] is not None else None,
            "compliance_status": r["compliance_status"],
            "rationale": r["supervisor_reasoning"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "read": False,
        }
        for r in rows
    ]
    return {"items": items, "count": len(items)}


@router.get("/{alert_id}")
async def get_alert(alert_id: str):
    """Fetch a single alert (decision) by its UUID."""
    import uuid
    try:
        did = uuid.UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="alert_id must be a UUID")

    row = await db.fetchrow(
        """
        SELECT decision_id, portfolio_id, ticker, action, confidence,
               supervisor_reasoning, compliance_status, created_at
        FROM decision.decisions
        WHERE decision_id = $1
        """,
        did,
    )
    if row is None:
        if not await db.is_available():
            raise HTTPException(status_code=503, detail="postgres unavailable")
        raise HTTPException(status_code=404, detail="alert not found")

    return {
        "alert_id": str(row["decision_id"]),
        "ticker": row["ticker"],
        "action": row["action"],
        "confidence": float(row["confidence"]) if row["confidence"] is not None else None,
        "compliance_status": row["compliance_status"],
        "rationale": row["supervisor_reasoning"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "read": False,
    }


@router.post("/{alert_id}/read")
async def mark_alert_read(alert_id: str):
    """Mark an alert as read.

    Implementation note: the source-of-truth ``read`` flag would belong on a
    separate ``notification.alerts`` table. For now we ACK it via Redis so
    the dashboard can hide it without re-querying Postgres.
    """
    import redis_cache
    ok = await redis_cache.set_json(f"alerts:read:{alert_id}", True, ttl_seconds=86400)
    return {"alert_id": alert_id, "read": True, "persisted": ok}