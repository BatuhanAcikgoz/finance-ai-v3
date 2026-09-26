"""Tests for the SMA20/50 + momentum decision logic.

Pure math — no DB needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the api-gateway src importable as if from the package root.
ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

from services.decision_loop import _decide_action, _sma  # noqa: E402


def _series(n: int, start: float = 100.0, step: float = 1.0) -> list[float]:
    return [start + i * step for i in range(n)]


def test_sma_handles_short_series():
    assert _sma([1, 2, 3], 5) is None
    assert _sma([1, 2, 3, 4, 5], 3) == 4.0
    assert _sma([], 5) is None


def test_decide_action_buy_on_uptrend():
    # Steadily rising series with positive 5d momentum -> BUY
    closes = _series(60, 100.0, 1.0)
    action, confidence, ev = _decide_action(closes)
    assert action == "BUY"
    assert 0.0 < confidence <= 0.95
    assert ev["bars_used"] == 60
    assert ev["sma20"] is not None and ev["sma50"] is not None
    assert ev["momentum_5d_pct"] > 0


def test_decide_action_sell_on_downtrend():
    closes = _series(60, 100.0, -1.0)
    action, confidence, _ = _decide_action(closes)
    assert action == "SELL"
    assert confidence > 0.0


def test_decide_action_hold_on_flat():
    # All same value: SMA20 == SMA50 == close, momentum = 0 -> HOLD
    closes = [100.0] * 60
    action, confidence, ev = _decide_action(closes)
    assert action == "HOLD"
    assert confidence == 0.30  # baseline (clamp(0.30 + 0, 0, 0.95))


def test_decide_action_insufficient_evidence():
    action, confidence, ev = _decide_action([100.0, 101.0])
    assert action == "INSUFFICIENT_EVIDENCE"
    assert confidence == 0.0
    assert "fewer_than_5_bars" in ev["reason"]
