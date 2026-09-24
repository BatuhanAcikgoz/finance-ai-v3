"""Market data endpoints (real Postgres + Qdrant integration).

Endpoints:
  GET /v1/market/symbols            → list active tickers from market_data.tickers
  GET /v1/market/ohlcv/{symbol}     → OHLCV bars from market_data.bars
  GET /v1/market/quote/{symbol}     → latest bar (most recent close)
  GET /v1/market/decisions          → recent decisions (alias of decisions/recent)
  GET /v1/market/index/{index_code} → latest index_values row

All endpoints degrade gracefully when Postgres is unreachable: they return
``{"items": [], "degraded": true, ...}`` rather than 5xx.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import db
import redis_cache

logger = logging.getLogger(__name__)
router = APIRouter()


# -- response models --------------------------------------------------------

class TickerInfo(BaseModel):
    ticker: str
    name: str
    sector: Optional[str] = None
    subsector: Optional[str] = None
    is_index: bool = False
    is_active: bool = True


class OHLCVBar(BaseModel):
    ts: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str


class Quote(BaseModel):
    ticker: str
    price: float
    change_pct: Optional[float] = None
    as_of: str
    volume: Optional[float] = None


# -- helpers ----------------------------------------------------------------

def _bar_to_dict(row: Any) -> dict:
    return {
        "ts": row["bar_start"].isoformat() if row["bar_start"] else None,
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "volume": float(row["volume"]),
        "timeframe": row["timeframe"],
    }


def _decision_to_dict(row: Any) -> dict:
    """Convert a decision.decisions row into the API response shape."""
    return {
        "decision_id": str(row["decision_id"]),
        "portfolio_id": str(row["portfolio_id"]),
        "ticker": row["ticker"],
        "action": row["action"],
        "confidence": float(row["confidence"]) if row["confidence"] is not None else None,
        "position_size_pct": float(row["position_size_pct"]) if row["position_size_pct"] is not None else None,
        "evidence_count": row["evidence_count"],
        "contradiction_score": float(row["contradiction_score"]) if row["contradiction_score"] is not None else None,
        "compliance_status": row["compliance_status"],
        "effective_at": row["effective_at"].isoformat() if row["effective_at"] else None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "data_completeness": row["data_completeness"],
    }


# -- endpoints --------------------------------------------------------------

@router.get("/symbols")
async def list_symbols(limit: int = Query(500, le=2000)):
    """All active tickers. Cached in Redis for 60s."""
    cache_key = f"market:symbols:{limit}"
    cached = await redis_cache.get_json(cache_key)
    if cached is not None:
        return cached

    rows = await db.fetch(
        """
        SELECT ticker, name, sector, subsector, is_index, is_active
        FROM market_data.tickers
        WHERE is_active = TRUE
        ORDER BY is_index DESC, ticker ASC
        LIMIT $1
        """,
        limit,
    )
    if not rows and not await db.is_available():
        # Graceful degraded response — empty list, signal unavailability.
        return {"items": [], "count": 0, "degraded": True}

    items = [
        {
            "ticker": r["ticker"],
            "name": r["name"],
            "sector": r["sector"],
            "subsector": r["subsector"],
            "is_index": bool(r["is_index"]),
            "is_active": bool(r["is_active"]),
        }
        for r in rows
    ]
    payload = {"items": items, "count": len(items)}
    await redis_cache.set_json(cache_key, payload, ttl_seconds=60)
    return payload


@router.get("/ohlcv/{symbol}")
async def get_ohlcv(
    symbol: str,
    timeframe: str = Query("1d", pattern="^(1m|5m|15m|60m|1d)$"),
    limit: int = Query(200, le=2000),
):
    """Latest OHLCV bars for a ticker, ordered by timestamp DESC."""
    symbol = symbol.upper()
    cache_key = f"market:ohlcv:{symbol}:{timeframe}:{limit}"
    cached = await redis_cache.get_json(cache_key)
    if cached is not None:
        return cached

    rows = await db.fetch(
        """
        SELECT ticker, timeframe, open, high, low, close, volume,
               bar_start, bar_end
        FROM market_data.bars
        WHERE ticker = $1 AND timeframe = $2
        ORDER BY bar_start DESC
        LIMIT $3
        """,
        symbol, timeframe, limit,
    )
    if not rows and not await db.is_available():
        raise HTTPException(
            status_code=503,
            detail="market data backend unavailable",
        )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"no OHLCV data for ticker {symbol} timeframe {timeframe}",
        )

    bars = [_bar_to_dict(r) for r in rows]
    payload = {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(bars),
        "bars": bars,
    }
    await redis_cache.set_json(cache_key, payload, ttl_seconds=30)
    return payload


@router.get("/quote/{symbol}")
async def get_quote(symbol: str):
    """Latest close (or last bar's close) for a ticker."""
    symbol = symbol.upper()
    cache_key = f"market:quote:{symbol}"
    cached = await redis_cache.get_json(cache_key)
    if cached is not None:
        return cached

    row = await db.fetchrow(
        """
        SELECT ticker, close, volume, bar_start
        FROM market_data.bars
        WHERE ticker = $1
        ORDER BY bar_start DESC
        LIMIT 1
        """,
        symbol,
    )
    if row is None:
        if not await db.is_available():
            raise HTTPException(
                status_code=503,
                detail="market data backend unavailable",
            )
        raise HTTPException(
            status_code=404,
            detail=f"no quote for ticker {symbol}",
        )

    # Day-change requires the previous bar — fetch it cheaply.
    prev = await db.fetchrow(
        """
        SELECT close FROM market_data.bars
        WHERE ticker = $1
        ORDER BY bar_start DESC
        OFFSET 1 LIMIT 1
        """,
        symbol,
    )
    change_pct: Optional[float] = None
    if prev is not None and float(prev["close"]) != 0:
        change_pct = (float(row["close"]) - float(prev["close"])) / float(prev["close"]) * 100.0

    payload = {
        "ticker": symbol,
        "price": float(row["close"]),
        "change_pct": change_pct,
        "volume": float(row["volume"]) if row["volume"] is not None else None,
        "as_of": row["bar_start"].isoformat() if row["bar_start"] else None,
    }
    await redis_cache.set_json(cache_key, payload, ttl_seconds=15)
    return payload


@router.get("/decisions")
async def market_decisions(limit: int = Query(50, le=200)):
    """Recent decisions — used by dashboards that want market+decisions on one page.

    Backed by the same Postgres table as ``/v1/decisions/recent``.
    """
    rows = await db.fetch(
        """
        SELECT decision_id, portfolio_id, ticker, action, confidence,
               position_size_pct, evidence_count, contradiction_score,
               compliance_status, effective_at, created_at, data_completeness
        FROM decision.decisions
        ORDER BY created_at DESC
        LIMIT $1
        """,
        limit,
    )
    if not rows and not await db.is_available():
        return {"items": [], "count": 0, "degraded": True}
    items = [_decision_to_dict(r) for r in rows]
    return {"items": items, "count": len(items)}


@router.get("/index/{index_code}")
async def get_index(index_code: str):
    """Latest value for a BIST index."""
    index_code = index_code.upper()
    cache_key = f"market:index:{index_code}"
    cached = await redis_cache.get_json(cache_key)
    if cached is not None:
        return cached

    row = await db.fetchrow(
        """
        SELECT index_code, value, change_pct, as_of
        FROM market_data.index_values
        WHERE index_code = $1
        ORDER BY as_of DESC
        LIMIT 1
        """,
        index_code,
    )
    if row is None:
        if not await db.is_available():
            raise HTTPException(status_code=503, detail="market data backend unavailable")
        raise HTTPException(status_code=404, detail=f"no data for index {index_code}")

    payload = {
        "index_code": row["index_code"],
        "value": float(row["value"]),
        "change_pct": float(row["change_pct"]) if row["change_pct"] is not None else None,
        "as_of": row["as_of"].isoformat() if row["as_of"] else None,
    }
    await redis_cache.set_json(cache_key, payload, ttl_seconds=30)
    return payload


@router.get("/indices")
async def list_indices():
    """Static list of well-known BIST indices (matches original skeleton)."""
    return {"indices": ["XU100", "XU030", "XBANK", "BIST-FIN", "BIST-IND", "BIST-SRV"]}