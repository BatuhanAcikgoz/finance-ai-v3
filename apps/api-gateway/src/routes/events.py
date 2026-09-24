"""Recent events endpoint — dashboard activity feed.

Builds a merged, time-ordered stream from:
  1. ``decision.decisions`` — decision.created events
  2. ``notification.alerts`` — alert.new events
  3. ``market_data.tickers`` — synthetic market.tick events (one per active
     ticker, every 30s; not persisted, generated on the fly)

Endpoints:
  GET /v1/events?limit=50   → paginated stream of recent events
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

import db

logger = logging.getLogger(__name__)
router = APIRouter()

# Synthetic tick interval — every 30s per ticker, bucketed by bar_start.
_TICK_INTERVAL_SECONDS = 30


def _err(error: str, detail: str) -> JSONResponse:
    """Standard 503 error response per gateway spec."""
    return JSONResponse(status_code=503, content={"error": error, "detail": detail})


def _ts_iso(v: Any) -> str | None:
    return v.isoformat() if v else None


@router.get("/")
async def list_events(limit: int = Query(50, le=200)):
    """Merge recent decisions + alerts + synthetic market ticks, newest first."""
    try:
        items: list[dict] = []

        # 1) Decisions
        decision_rows = await db.fetch(
            """
            SELECT decision_id, ticker, action, confidence, created_at
            FROM decision.decisions
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
        for r in decision_rows:
            confidence = r.get("confidence")
            confidence_str = (
                f"{float(confidence):.0%}"
                if confidence is not None else "n/a"
            )
            items.append({
                "ts": _ts_iso(r.get("created_at")),
                "type": "decision.created",
                "ticker": r["ticker"],
                "summary": f"{r['action']} ({confidence_str} confidence)",
            })

        # 2) Alerts
        alert_rows = await db.fetch(
            """
            SELECT alert_id, ticker, grade, title, created_at
            FROM notification.alerts
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
        for r in alert_rows:
            items.append({
                "ts": _ts_iso(r.get("created_at")),
                "type": "alert.new",
                "ticker": r.get("ticker"),
                "summary": f"{r['grade']}: {r['title']}",
            })

        # 3) Synthetic market ticks (one per active ticker per 30s bucket)
        ticker_rows = await db.fetch(
            """
            SELECT ticker, name
            FROM market_data.tickers
            WHERE is_active = TRUE
            """
        )
        if ticker_rows:
            now = datetime.now(timezone.utc)
            # Bucket "now" into the 30s window it falls in.
            bucket_start = now.replace(
                second=(now.second // _TICK_INTERVAL_SECONDS) * _TICK_INTERVAL_SECONDS,
                microsecond=0,
            )
            # Emit one synthetic tick per ticker at this bucket — only if we
            # have at least one *real* event to anchor against (so empty
            # timelines stay empty rather than being filled with ghosts).
            if items:
                for t in ticker_rows:
                    items.append({
                        "ts": bucket_start.isoformat(),
                        "type": "market.tick",
                        "ticker": t["ticker"],
                        "summary": f"synthetic tick for {t['name']}",
                    })

        # Sort newest-first, dedupe by (ts, type, ticker, summary) for stability.
        seen: set[tuple] = set()
        deduped: list[dict] = []
        for it in sorted(items, key=lambda x: x.get("ts") or "", reverse=True):
            key = (it.get("ts"), it.get("type"), it.get("ticker"), it.get("summary"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(it)

        # Re-fetch ticker rows to ensure we don't truncate beyond limit.
        return {"items": deduped[:limit], "count": min(len(deduped), limit)}
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("events.list.error: %s", str(exc))
        return _err("list_events_failed", str(exc))
