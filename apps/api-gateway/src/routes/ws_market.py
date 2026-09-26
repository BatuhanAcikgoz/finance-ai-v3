"""WebSocket market data feed (issue #1 / FR-005).

A synthetic tick generator produces a tick every N seconds per active ticker.
The WS endpoint broadcasts each tick to all connected clients. Clients can
connect to /ws/market for the full feed, or /ws/market/{symbol} for a single
symbol snapshot+stream.

Architecture:
  TickEngine runs as a single background task started from the api-gateway
  lifespan. It generates ticks deterministically from the last bar in the
  database (so the dashboard sees prices that move around real values rather
  than random noise).

  ConnectionManager keeps a set of open WebSocket connections. On each tick,
  the engine calls manager.broadcast(json_payload). On disconnect, the
  handler removes its socket from the set.

This is intentionally simple. A production version would back the manager
with Redis pub/sub for cross-process broadcasting.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import time
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import db

logger = logging.getLogger(__name__)

router = APIRouter()


# -------- connection manager ------------------------------------------------

class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, default=str)
        async with self._lock:
            stale: list[WebSocket] = []
            for ws in list(self._connections):
                try:
                    await ws.send_text(data)
                except Exception:  # noqa: BLE001
                    stale.append(ws)
            for ws in stale:
                self._connections.discard(ws)


manager = ConnectionManager()


# -------- tick engine -------------------------------------------------------

@dataclass
class TickState:
    ticker: str
    last: float
    bid: float
    ask: float
    volume: float
    drift: float = 0.0  # accumulated bias for the random walk


async def _load_state(pool) -> dict[str, TickState]:
    """Seed tick state from the last bar in market_data.bars per ticker."""
    rows = await pool.fetch(
        """
        SELECT DISTINCT ON (b.ticker) b.ticker, b.close, b.volume
        FROM market_data.bars b
        JOIN market_data.tickers t ON t.ticker = b.ticker
        WHERE t.is_active = TRUE AND t.is_index = FALSE
        ORDER BY b.ticker, b.bar_start DESC
        """
    )
    states: dict[str, TickState] = {}
    for r in rows:
        last = float(r["close"])
        states[r["ticker"]] = TickState(
            ticker=r["ticker"],
            last=last,
            bid=last * 0.9995,
            ask=last * 1.0005,
            volume=float(r["volume"]) / 100.0,
        )
    return states


def _step(state: TickState) -> dict[str, Any]:
    """Random-walk tick generator (mean-reverting around last price)."""
    sigma = max(0.0005, 0.005)  # ~0.5% std dev per tick
    shock = random.gauss(0, sigma) * state.last
    # mean-revert toward last by 0.05 per tick so prices don't drift off
    state.drift = state.drift * 0.95 + shock * 0.05
    new_last = max(0.01, state.last + state.drift)
    state.bid = new_last * 0.9995
    state.ask = new_last * 1.0005
    state.volume += random.uniform(0, max(1.0, state.last * 0.5))
    state.last = new_last
    return {
        "ts": time.time(),
        "ticker": state.ticker,
        "last": round(state.last, 4),
        "bid": round(state.bid, 4),
        "ask": round(state.ask, 4),
        "volume": round(state.volume, 2),
    }


class TickEngine:
    def __init__(self, interval_seconds: float | None = None) -> None:
        self.interval = float(
            interval_seconds
            or os.getenv("WS_TICK_INTERVAL_S", "2.0")
        )
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._states: dict[str, TickState] = {}
        self.ticks_emitted: int = 0
        self.last_tick_at: float | None = None

    async def _run(self) -> None:
        logger.info("tick_engine.started interval_s=%.2f", self.interval)
        pool = await db.get_pool()
        if pool is not None:
            try:
                self._states = await _load_state(pool)
                logger.info("tick_engine.seeded tickers=%d", len(self._states))
            except Exception:  # noqa: BLE001
                logger.exception("tick_engine.seed_failed")
        if not self._states:
            # Synthetic fallback so the engine always has something to emit.
            for ticker in ("THYAO", "GARAN", "AKBNK", "KCHOL", "ASELS"):
                self._states[ticker] = TickState(
                    ticker=ticker, last=100.0 + random.random() * 50.0,
                    bid=0.0, ask=0.0, volume=0.0,
                )

        while not self._stop.is_set():
            try:
                for state in self._states.values():
                    payload = _step(state)
                    await manager.broadcast(payload)
                    self.ticks_emitted += 1
                self.last_tick_at = time.time()
            except Exception:  # noqa: BLE001
                logger.exception("tick_engine.cycle_failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                continue
        logger.info("tick_engine.stopped")

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="tick-engine")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=3)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None


_engine: TickEngine | None = None


def get_engine() -> TickEngine:
    global _engine
    if _engine is None:
        _engine = TickEngine()
    return _engine


# -------- WebSocket endpoints ----------------------------------------------

@router.websocket("/ws/market")
async def ws_market_all(ws: WebSocket) -> None:
    """Broadcast every tick from every ticker."""
    await manager.connect(ws)
    # Greet the client so it sees immediate activity.
    try:
        await ws.send_text(json.dumps({
            "type": "hello",
            "ts": time.time(),
            "msg": "subscribed to all tickers",
            "active_tickers": sorted(list(get_engine()._states.keys())),
        }))
        while True:
            # We don't expect to receive anything; just keep the socket alive.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.exception("ws_market_all.error")
    finally:
        await manager.disconnect(ws)


@router.websocket("/ws/market/{symbol}")
async def ws_market_symbol(ws: WebSocket, symbol: str) -> None:
    """Filter the broadcast feed to a single ticker.

    On connect, sends a 'snapshot' message with the current engine state.
    Then forwards only matching tick events.
    """
    symbol = symbol.upper()
    await manager.connect(ws)
    try:
        engine = get_engine()
        snapshot = None
        st = engine._states.get(symbol)
        if st is not None:
            snapshot = {
                "type": "snapshot",
                "ts": time.time(),
                "ticker": symbol,
                "last": round(st.last, 4),
                "bid": round(st.bid, 4),
                "ask": round(st.ask, 4),
                "volume": round(st.volume, 2),
            }
        await ws.send_text(json.dumps(snapshot or {
            "type": "snapshot",
            "ts": time.time(),
            "ticker": symbol,
            "last": None,
            "msg": "no data for this ticker; will forward ticks once available",
        }))
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.exception("ws_market_symbol.error symbol=%s", symbol)
    finally:
        await manager.disconnect(ws)


@router.get("/ws/stats")
async def ws_stats() -> dict:
    """Engine + connection stats — useful for the dashboard."""
    engine = get_engine()
    return {
        "connections": len(manager._connections),
        "active_tickers": sorted(list(engine._states.keys())),
        "ticks_emitted": engine.ticks_emitted,
        "last_tick_at": engine.last_tick_at,
        "interval_seconds": engine.interval,
    }


__all__ = ["router", "get_engine", "manager"]
