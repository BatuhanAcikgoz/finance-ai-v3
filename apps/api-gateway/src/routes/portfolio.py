"""Portfolio endpoints — backed by ``portfolio.portfolios`` + ``portfolio.holdings``.

Endpoints:
  GET  /v1/portfolio                       → list portfolios (default if none)
  GET  /v1/portfolio/{id}/state            → aggregate state + holdings
  GET  /v1/portfolio/{id}/holdings/{ticker}→ single holding + recent decisions + risk
  POST /v1/portfolio                       → create new (dev convenience)

When the database is unreachable, list endpoints degrade with ``degraded: True``
and an empty ``items`` array. State / single-holding endpoints return 503.
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

class CreatePortfolioRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    base_currency: str = Field("TRY", min_length=3, max_length=3)
    user_id: Optional[str] = Field(
        None,
        description="Owner UUID; auto-generated for dev convenience if omitted.",
    )


class CreatePortfolioResponse(BaseModel):
    portfolio_id: str
    name: str
    base_currency: str
    created_at: str
    status: str = "created"


# -- helpers ----------------------------------------------------------------

def _portfolio_row_to_dict(row: Any) -> dict:
    """Convert a ``portfolio.portfolios`` row to the API response shape."""
    return {
        "portfolio_id": str(row["portfolio_id"]),
        "name": row["name"],
        "base_currency": row["base_currency"],
        "user_id": str(row["user_id"]) if row.get("user_id") else None,
        "risk_budget_pct": float(row["risk_budget_pct"])
            if row.get("risk_budget_pct") is not None else None,
        "max_position_pct": float(row["max_position_pct"])
            if row.get("max_position_pct") is not None else None,
        "max_sector_pct": float(row["max_sector_pct"])
            if row.get("max_sector_pct") is not None else None,
        "created_at": row["created_at"].isoformat()
            if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat()
            if row.get("updated_at") else None,
    }


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _hhi(weights: list[float]) -> float:
    """Herfindahl-Hirschman index of weights (already in 0..1)."""
    return sum(w * w for w in weights)


# -- endpoints --------------------------------------------------------------

@router.get("/")
async def list_portfolios(limit: int = Query(50, le=200)):
    """List all portfolios. If none exist, return a synthesized 'default' entry
    so the dashboard renders something rather than an empty state.
    """
    try:
        rows = await db.fetch(
            """
            SELECT portfolio_id, user_id, name, base_currency,
                   risk_budget_pct, max_position_pct, max_sector_pct,
                   created_at, updated_at
            FROM portfolio.portfolios
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )

        items = [_portfolio_row_to_dict(r) for r in rows]

        # Synthesize a "default" entry if the table is empty so the UI
        # always has at least one row to render.
        if not items:
            if not await db.is_available():
                return {"items": [], "count": 0, "degraded": True}
            items = [
                {
                    "portfolio_id": "default",
                    "name": "Default Portfolio",
                    "base_currency": "TRY",
                    "user_id": None,
                    "risk_budget_pct": 0.03,
                    "max_position_pct": 0.25,
                    "max_sector_pct": 0.40,
                    "created_at": None,
                    "updated_at": None,
                    "synthesized": True,
                }
            ]

        return {"items": items, "count": len(items)}
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("portfolio.list.error: %s", str(exc))
        return _err("list_portfolios_failed", str(exc))


@router.get("/{portfolio_id}/state")
async def get_portfolio_state(portfolio_id: str):
    """Aggregate portfolio state + holdings list.

    All monetary figures are in the portfolio's base currency (TRY by default).
    Quantities / cost basis come from ``portfolio.holdings``; current_value and
    unrealized_pnl are stored columns. ``weights_drift_hhi`` measures
    concentration + target deviation: ``sum((weight_pct - target_weight_pct)^2)``.
    """
    try:
        # Treat the synthesized default specially — return an empty state.
        if portfolio_id == "default":
            return {
                "portfolio": {
                    "portfolio_id": "default",
                    "name": "Default Portfolio",
                    "base_currency": "TRY",
                    "synthesized": True,
                },
                "total_value_try": 0.0,
                "total_cost_try": 0.0,
                "unrealized_pnl_try": 0.0,
                "daily_pnl_pct": 0.0,
                "weights_drift_hhi": 0.0,
                "holdings": [],
                "degraded": not await db.is_available(),
            }

        # 1) Portfolio meta
        portfolio_row = await db.fetchrow(
            """
            SELECT portfolio_id, user_id, name, base_currency,
                   risk_budget_pct, max_position_pct, max_sector_pct,
                   created_at, updated_at
            FROM portfolio.portfolios
            WHERE portfolio_id = $1
            """,
            uuid.UUID(portfolio_id),
        )
        if portfolio_row is None:
            if not await db.is_available():
                raise HTTPException(status_code=503, detail="postgres unavailable")
            raise HTTPException(status_code=404, detail="portfolio not found")

        # 2) Holdings
        holding_rows = await db.fetch(
            """
            SELECT h.ticker, h.shares, h.cost_basis_try, h.target_weight,
                   h.current_price, h.current_value, h.unrealized_pnl,
                   h.updated_at,
                   t.name AS ticker_name
            FROM portfolio.holdings h
            LEFT JOIN market_data.tickers t ON t.ticker = h.ticker
            WHERE h.portfolio_id = $1
            ORDER BY h.current_value DESC NULLS LAST, h.ticker ASC
            """,
            uuid.UUID(portfolio_id),
        )

        # 3) Aggregate — first pass: compute totals so the second pass can
        # compute portfolio-relative weights correctly.
        total_value = 0.0
        total_cost = 0.0
        for r in holding_rows:
            current_value = _to_float(r["current_value"]) or 0.0
            cost_basis_try = _to_float(r["cost_basis_try"]) or 0.0
            shares = _to_float(r["shares"]) or 0.0
            total_value += current_value
            total_cost += cost_basis_try * shares

        # Second pass: per-holding weights + drift HHI.
        drift_sq_sum = 0.0
        holdings_out = []
        for r in holding_rows:
            current_value = _to_float(r["current_value"]) or 0.0
            cost_basis_try = _to_float(r["cost_basis_try"]) or 0.0
            shares = _to_float(r["shares"]) or 0.0
            target_w = _to_float(r["target_weight"]) or 0.0
            unrealized = _to_float(r["unrealized_pnl"]) or 0.0
            current_price = _to_float(r["current_price"])

            weight_pct = (current_value / total_value) if total_value > 0 else 0.0
            drift_pct = weight_pct - target_w
            drift_sq_sum += drift_pct * drift_pct

            holdings_out.append({
                "ticker": r["ticker"],
                "name": r["ticker_name"] or r["ticker"],
                "quantity": shares,
                "cost_basis": cost_basis_try,
                "current_value": current_value,
                "weight_pct": round(weight_pct, 6),
                "target_weight_pct": target_w,
                "drift_pct": round(drift_pct, 6),
                "daily_pnl_pct": 0.0,  # not stored; placeholder until tick feed exists
                "unrealized_pnl": unrealized,
                "current_price": current_price,
                "updated_at": r["updated_at"].isoformat()
                    if r.get("updated_at") else None,
            })

        unrealized_pnl = total_value - total_cost
        daily_pnl_pct = 0.0  # aggregate daily P&L not stored; UI treats as 0
        hhi = drift_sq_sum

        return {
            "portfolio": _portfolio_row_to_dict(portfolio_row),
            "total_value_try": round(total_value, 2),
            "total_cost_try": round(total_cost, 2),
            "unrealized_pnl_try": round(unrealized_pnl, 2),
            "daily_pnl_pct": daily_pnl_pct,
            "weights_drift_hhi": round(hhi, 6),
            "holdings": holdings_out,
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("portfolio.state.error: %s", str(exc))
        return _err("get_portfolio_state_failed", str(exc))


@router.get("/{portfolio_id}/holdings/{ticker}")
async def get_holding(portfolio_id: str, ticker: str):
    """Single holding detail + recent decisions + risk metrics (beta, VaR)."""
    try:
        ticker = ticker.upper()

        holding_row = await db.fetchrow(
            """
            SELECT h.ticker, h.shares, h.cost_basis_try, h.target_weight,
                   h.current_price, h.current_value, h.unrealized_pnl,
                   h.updated_at,
                   t.name AS ticker_name
            FROM portfolio.holdings h
            LEFT JOIN market_data.tickers t ON t.ticker = h.ticker
            WHERE h.portfolio_id = $1 AND h.ticker = $2
            """,
            uuid.UUID(portfolio_id), ticker,
        )
        if holding_row is None:
            if not await db.is_available():
                raise HTTPException(status_code=503, detail="postgres unavailable")
            raise HTTPException(
                status_code=404,
                detail=f"holding {ticker} not in portfolio {portfolio_id}",
            )

        # Recent decisions on this ticker.
        decision_rows = await db.fetch(
            """
            SELECT decision_id, action, confidence, effective_at
            FROM decision.decisions
            WHERE ticker = $1
            ORDER BY effective_at DESC
            LIMIT 10
            """,
            ticker,
        )
        recent_decisions = [
            {
                "decision_id": str(r["decision_id"]),
                "action": r["action"],
                "confidence": _to_float(r["confidence"]),
                "effective_at": r["effective_at"].isoformat()
                    if r.get("effective_at") else None,
            }
            for r in decision_rows
        ]

        # Risk metrics — beta / VaR placeholder (not stored on holdings).
        risk_metrics = {
            "beta": None,
            "var_95_1d_pct": None,
        }

        return {
            "holding": {
                "ticker": holding_row["ticker"],
                "name": holding_row["ticker_name"] or holding_row["ticker"],
                "quantity": _to_float(holding_row["shares"]),
                "cost_basis": _to_float(holding_row["cost_basis_try"]),
                "current_value": _to_float(holding_row["current_value"]),
                "target_weight_pct": _to_float(holding_row["target_weight"]),
                "unrealized_pnl": _to_float(holding_row["unrealized_pnl"]),
                "current_price": _to_float(holding_row["current_price"]),
                "updated_at": holding_row["updated_at"].isoformat()
                    if holding_row.get("updated_at") else None,
            },
            "recent_decisions": recent_decisions,
            "risk_metrics": risk_metrics,
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("portfolio.holding.error: %s", str(exc))
        return _err("get_holding_failed", str(exc))


@router.post("/", response_model=CreatePortfolioResponse, status_code=201)
async def create_portfolio(req: CreatePortfolioRequest):
    """Create a new portfolio (dev convenience — no auth required)."""
    try:
        user_uuid = (
            uuid.UUID(req.user_id) if req.user_id else uuid.uuid4()
        )
        new_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        status_msg = await db.execute(
            """
            INSERT INTO portfolio.portfolios (
                portfolio_id, user_id, name, base_currency,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4,
                $5, $5
            )
            """,
            new_id, user_uuid, req.name, req.base_currency.upper(), now,
        )
        if not status_msg:
            if not await db.is_available():
                raise HTTPException(status_code=503, detail="postgres unavailable")
            raise HTTPException(status_code=500, detail="insert failed")

        return CreatePortfolioResponse(
            portfolio_id=str(new_id),
            name=req.name,
            base_currency=req.base_currency.upper(),
            created_at=now.isoformat(),
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("portfolio.create.error: %s", str(exc))
        return _err("create_portfolio_failed", str(exc))
