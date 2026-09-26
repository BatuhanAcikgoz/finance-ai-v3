"""Phase-1 live decision loop.

Issue #7: every N seconds, walk through market_data.tickers and emit a real
decision for each using a deterministic SMA20/50 + momentum strategy. The
dashboard already renders /v1/decisions/recent — this module just feeds it.

No LLM calls. Pure rule-based. Safe to run in the api-gateway lifespan.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg

from config import settings
import db

logger = logging.getLogger(__name__)


# -------- pure-math helpers (testable without DB) --------

def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window or window <= 0:
        return None
    return sum(values[-window:]) / window


def _decide_action(closes: list[float]) -> tuple[str, float, dict[str, Any]]:
    """Return (action, confidence, evidence).

    Rule: BUY  if close > sma20 > sma50 AND 5d momentum >  2%
          SELL if close < sma20 < sma50 AND 5d momentum < -2%
          HOLD otherwise
    Confidence = clamp(0.30 + abs(momentum)*5, 0.0, 0.95)
    """
    if len(closes) < 5:
        return "INSUFFICIENT_EVIDENCE", 0.0, {"reason": "fewer_than_5_bars"}

    last = closes[-1]
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    momentum = (
        (last - closes[-6]) / closes[-6] if len(closes) >= 6 and closes[-6] else 0.0
    )

    action = "HOLD"
    if sma20 is not None and sma50 is not None:
        if last > sma20 > sma50 and momentum > 0.02:
            action = "BUY"
        elif last < sma20 < sma50 and momentum < -0.02:
            action = "SELL"

    confidence = max(0.0, min(0.95, 0.30 + abs(momentum) * 5.0))

    evidence = {
        "bars_used": len(closes),
        "last_close": last,
        "sma20": sma20,
        "sma50": sma50,
        "momentum_5d_pct": round(momentum * 100, 3),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": "sma20_50_momentum_v1",
    }
    return action, round(confidence, 3), evidence


# -------- DB helpers --------

async def _fetch_tickers(pool: asyncpg.Pool) -> list[str]:
    rows = await pool.fetch(
        "SELECT ticker FROM market_data.tickers WHERE is_active = TRUE AND is_index = FALSE"
    )
    return [r["ticker"] for r in rows]


async def _fetch_closes(pool: asyncpg.Pool, ticker: str, limit: int = 80) -> list[float]:
    rows = await pool.fetch(
        """
        SELECT close FROM market_data.bars
        WHERE ticker = $1 AND timeframe = '1d'
        ORDER BY bar_start DESC LIMIT $2
        """,
        ticker,
        limit,
    )
    # bars come back newest-first; reverse so closes[-1] is the latest.
    return [float(r["close"]) for r in rows][::-1]


async def _insert_decision(
    pool: asyncpg.Pool,
    ticker: str,
    action: str,
    confidence: float,
    evidence: dict[str, Any],
) -> str:
    decision_id = str(uuid.uuid4())
    portfolio_id = "00000000-0000-0000-0000-000000000001"  # default placeholder
    # The default portfolio in dev is the string 'default' but the column is UUID,
    # so we use a stable UUID. Tests can match on ticker.
    position_size_pct = round(min(confidence * 0.15, 0.10), 4)

    import json as _json
    now = datetime.now(timezone.utc)
    await pool.execute(
        """
        INSERT INTO decision.decisions (
            decision_id, portfolio_id, ticker, action, confidence,
            position_size_pct, evidence, evidence_count, contradiction_score,
            compliance_status, effective_at, data_completeness,
            prompt_versions
        ) VALUES (
            $1::uuid, $2::uuid, $3, $4, $5, $6, $7::jsonb, $8, 0.0,
            'PENDING', $9, 'PARTIAL', $10::jsonb
        )
        ON CONFLICT DO NOTHING
        """,
        decision_id,
        portfolio_id,
        ticker,
        action,
        confidence,
        position_size_pct,
        _json.dumps(evidence),
        evidence.get("bars_used", 0),
        now,
        _json.dumps({"strategy": "sma20_50_momentum_v1"}),
    )
    return decision_id


# -------- background loop --------

class DecisionLoop:
    """Async scheduler that emits one decision per active ticker every N seconds."""

    def __init__(self, interval_seconds: int | None = None) -> None:
        self.interval = int(
            interval_seconds
            or os.getenv("DECISION_LOOP_INTERVAL_S", "60")
        )
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None
        self.last_run_at: datetime | None = None
        self.last_run_count: int = 0

    async def _cycle(self) -> None:
        pool = await db.get_pool()
        if pool is None:
            logger.warning("decision_loop.cycle skipped reason=pool_unavailable")
            return
        try:
            tickers = await _fetch_tickers(pool)
            count = 0
            for ticker in tickers:
                try:
                    closes = await _fetch_closes(pool, ticker)
                    if not closes:
                        continue
                    action, confidence, evidence = _decide_action(closes)
                    await _insert_decision(pool, ticker, action, confidence, evidence)
                    count += 1
                except Exception as exc:  # noqa: BLE001
                    logger.exception("decision_loop.ticker_failed ticker=%s err=%s", ticker, exc)
            self.last_run_at = datetime.now(timezone.utc)
            self.last_run_count = count
            logger.info("decision_loop.cycle_done processed=%d total_tickers=%d",
                        count, len(tickers))
        except Exception:  # noqa: BLE001
            logger.exception("decision_loop.cycle_failed")

    async def _run(self) -> None:
        logger.info("decision_loop.started interval_s=%d", self.interval)
        while not self._stop.is_set():
            await self._cycle()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                continue
        logger.info("decision_loop.stopped")

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="decision-loop")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None


_loop: DecisionLoop | None = None


def get_loop() -> DecisionLoop:
    global _loop
    if _loop is None:
        _loop = DecisionLoop()
    return _loop


__all__ = [
    "DecisionLoop",
    "_decide_action",
    "_sma",
    "_fetch_tickers",
    "_fetch_closes",
    "_insert_decision",
    "get_loop",
]
