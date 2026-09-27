"""Backtest endpoints — backed by ``analysis.backtest_runs``.

Endpoints:
  GET  /v1/backtest                    → list runs
  POST /v1/backtest/run                → enqueue a new run (non-blocking)
  POST /v1/backtest/{run_id}/approve   → mark a run as approved

Schema (from ``infra/docker/postgres/init.sql``):
    run_id UUID, started_at, ended_at, scope JSONB, hit_rate,
    total_trades, winning_trades, losing_trades, avg_return,
    sharpe, max_drawdown, proposed_weight_adjustments JSONB,
    approved BOOLEAN, approved_at TIMESTAMPTZ
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import db

logger = logging.getLogger(__name__)
router = APIRouter()


def _err(error: str, detail: str) -> JSONResponse:
    """Standard 503 error response per gateway spec."""
    return JSONResponse(status_code=503, content={"error": error, "detail": detail})


# -- request/response models ------------------------------------------------

class RunBacktestRequest(BaseModel):
    """Optional body — start a new run with default scope if omitted."""
    scope: Optional[dict] = Field(
        default_factory=lambda: {"universe": "BIST100", "period": "1y"},
        description="Scope object stored in analysis.backtest_runs.scope",
    )


class RunBacktestResponse(BaseModel):
    run_id: str
    status: str = "queued"


class ApproveResponse(BaseModel):
    run_id: str
    status: str = "approved"
    approved_at: str


# -- helpers ----------------------------------------------------------------

def _row_to_dict(row: Any) -> dict:
    def _f(v: Any) -> Optional[float]:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return float(v)
        return float(v)
    return {
        "run_id": str(row["run_id"]),
        "started_at": row["started_at"].isoformat()
            if row.get("started_at") else None,
        "ended_at": row["ended_at"].isoformat()
            if row.get("ended_at") else None,
        "hit_rate": _f(row.get("hit_rate")),
        "total_trades": row.get("total_trades"),
        "winning_trades": row.get("winning_trades"),
        "losing_trades": row.get("losing_trades"),
        "avg_return": _f(row.get("avg_return")),
        "sharpe": _f(row.get("sharpe")),
        "max_drawdown": _f(row.get("max_drawdown")),
        "approved": bool(row.get("approved"))
            if row.get("approved") is not None else None,
    }


def _json(value) -> str:
    import json
    return json.dumps(value, default=str)


# -- endpoints --------------------------------------------------------------

@router.get("/")
async def list_backtests(limit: int = 50):
    """List backtest runs, newest first."""
    try:
        rows = await db.fetch(
            """
            SELECT run_id, started_at, ended_at, hit_rate, total_trades,
                   winning_trades, losing_trades, avg_return, sharpe,
                   max_drawdown, approved
            FROM analysis.backtest_runs
            ORDER BY started_at DESC
            LIMIT $1
            """,
            limit,
        )
        if not rows and not await db.is_available():
            return {"items": [], "count": 0, "degraded": True}
        items = [_row_to_dict(r) for r in rows]
        return {"items": items, "count": len(items)}
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("backtest.list.error: %s", str(exc))
        return _err("list_backtests_failed", str(exc))


@router.post("/run", response_model=RunBacktestResponse, status_code=201)
async def run_backtest(req: RunBacktestRequest = RunBacktestRequest()):
    """Insert a queued run, execute the backtest, and persist results.

    Issue #3 / FR-072..FR-074: the backtest is now actually computed in an
    asyncio.create_task so the POST returns immediately and the row gets
    filled in once ``run()`` completes (or the task fails, in which case we
    just leave ended_at NULL — visible to the dashboard as 'pending').
    """
    from services.backtest_runner import _Bar, run as run_bt

    try:
        new_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        status_msg = await db.execute(
            """
            INSERT INTO analysis.backtest_runs (
                run_id, started_at, scope
            ) VALUES (
                $1, $2, $3::jsonb
            )
            """,
            new_id, now, _json(req.scope or {}),
        )
        if not status_msg:
            if not await db.is_available():
                raise HTTPException(status_code=503, detail="postgres unavailable")
            raise HTTPException(status_code=500, detail="insert failed")

        async def _execute() -> None:
            try:
                pool = await db.get_pool()
                if pool is None:
                    return
                tickers = await pool.fetch(
                    "SELECT ticker FROM market_data.tickers "
                    "WHERE is_active = TRUE AND is_index = FALSE"
                )
                if not tickers:
                    return
                bars_by_ticker: dict[str, list[_Bar]] = {}
                for r in tickers:
                    rows = await pool.fetch(
                        """
                        SELECT open, close FROM market_data.bars
                        WHERE ticker = $1 AND timeframe = '1d'
                        ORDER BY bar_start DESC LIMIT 365
                        """,
                        r["ticker"],
                    )
                    bars = list(reversed(rows))
                    bars_by_ticker[r["ticker"]] = [
                        _Bar(close=float(b["close"]), open=float(b["open"]))
                        for b in bars
                    ]
                metrics = run_bt(bars_by_ticker)
                await pool.execute(
                    """
                    UPDATE analysis.backtest_runs
                    SET ended_at = NOW(),
                        hit_rate = $2, total_trades = $3,
                        winning_trades = $4, losing_trades = $5,
                        avg_return = $6, sharpe = $7, max_drawdown = $8
                    WHERE run_id = $1
                    """,
                    new_id,
                    metrics["hit_rate"],
                    metrics["total_trades"],
                    metrics["winning_trades"],
                    metrics["losing_trades"],
                    metrics["avg_return"],
                    metrics["sharpe"],
                    metrics["max_drawdown"],
                )
            except Exception:  # noqa: BLE001
                logger.exception("backtest.execute.failed run_id=%s", new_id)

        import asyncio
        asyncio.create_task(_execute())

        return RunBacktestResponse(run_id=str(new_id), status="queued")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("backtest.run.error: %s", str(exc))
        return _err("run_backtest_failed", str(exc))


@router.post("/{run_id}/approve", response_model=ApproveResponse)
async def approve_backtest(run_id: str):
    """Mark a run as approved; record ``approved_at`` timestamp."""
    try:
        try:
            run_uuid = uuid.UUID(run_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="run_id must be a UUID")

        now = datetime.now(timezone.utc)
        status_msg = await db.execute(
            """
            UPDATE analysis.backtest_runs
            SET approved = TRUE, approved_at = $2
            WHERE run_id = $1
            """,
            run_uuid, now,
        )
        # asyncpg returns "UPDATE N" — empty when no row matched OR pool is
        # unavailable (db.execute returns "" in the latter case).
        if not status_msg:
            if not await db.is_available():
                raise HTTPException(status_code=503, detail="postgres unavailable")
            raise HTTPException(status_code=404, detail="backtest run not found")
        # Distinguish "0 rows updated" from "pool unavailable" — db.execute
        # always returns "UPDATE N" string when the UPDATE ran.
        if status_msg and status_msg.startswith("UPDATE 0"):
            raise HTTPException(status_code=404, detail="backtest run not found")

        return ApproveResponse(
            run_id=str(run_uuid),
            status="approved",
            approved_at=now.isoformat(),
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("backtest.approve.error: %s", str(exc))
        return _err("approve_backtest_failed", str(exc))
