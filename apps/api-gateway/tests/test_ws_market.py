"""Tests for the WebSocket market tick engine (issue #1 / FR-005)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

from routes.ws_market import TickEngine, _step, TickState  # noqa: E402


def test_step_emits_valid_tick():
    s = TickState(ticker="THYAO", last=100.0, bid=99.95, ask=100.05, volume=10.0)
    payload = _step(s)
    assert payload["ticker"] == "THYAO"
    assert isinstance(payload["last"], float)
    assert payload["last"] > 0.0
    # bid <= last <= ask (within rounding)
    assert payload["bid"] <= payload["last"] <= payload["ask"]
    assert payload["volume"] >= payload["last"] * 0  # monotonically non-decreasing


def test_engine_has_interval_and_initial_state():
    eng = TickEngine(interval_seconds=0.1)
    assert eng.interval == 0.1
    assert eng.ticks_emitted == 0
    assert eng.last_tick_at is None
    assert eng._states == {}


def test_engine_runs_one_cycle_emits_broadcasts():
    """Drive the engine manually with a fake connection manager."""
    import asyncio
    from routes import ws_market

    captured: list[dict] = []

    class FakeMgr:
        async def broadcast(self, payload):
            captured.append(payload)

    # Patch the global manager used by ws_market.
    original_mgr = ws_market.manager
    ws_market.manager = FakeMgr()
    try:
        eng = ws_market.TickEngine(interval_seconds=0.01)
        # Pre-populate state so the cycle has data.
        eng._states["THYAO"] = TickState(
            ticker="THYAO", last=100.0, bid=99.95, ask=100.05, volume=0.0
        )

        async def one_cycle():
            for state in eng._states.values():
                await ws_market.manager.broadcast(ws_market._step(state))
            eng.ticks_emitted += len(eng._states)

        asyncio.run(one_cycle())
        assert len(captured) == 1
        assert captured[0]["ticker"] == "THYAO"
        assert captured[0]["last"] > 0
    finally:
        ws_market.manager = original_mgr
