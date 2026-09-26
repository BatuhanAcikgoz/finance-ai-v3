"""Tests for the SMA20/50 crossover backtest (issue #3 / FR-072..FR-074)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

from services.backtest_runner import _Bar, run  # noqa: E402


def _series(n: int, start: float = 100.0, step: float = 1.0) -> list[_Bar]:
    return [_Bar(close=start + i * step, open=start + i * step) for i in range(n)]


def test_run_with_no_bars_returns_zero_metrics():
    out = run({})
    assert out == {
        "hit_rate": 0.0,
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "avg_return": 0.0,
        "sharpe": 0.0,
        "max_drawdown": 0.0,
    }


def test_run_with_short_series_returns_zero_trades():
    bars = { "T1": _series(20) }   # < 50 days, no signal
    out = run(bars)
    assert out["total_trades"] == 0


def test_run_uptrend_produces_some_trades():
    bars = { "T1": _series(120, step=0.5) }
    out = run(bars)
    assert out["total_trades"] > 0
    # Strictly rising -> every trade should win.
    assert out["winning_trades"] == out["total_trades"]
    assert out["losing_trades"] == 0
    assert 0.0 < out["hit_rate"] <= 1.0


def test_run_downtrend_produces_no_winning_trades():
    # Strictly falling bars never trigger the 'uptrend' entry (long-only
    # strategy), so the runner simply produces no trades. We assert that
    # the result is well-formed with zero winners rather than expecting
    # losing trades from a long-only strategy.
    bars = { "T1": _series(120, step=-0.5) }
    out = run(bars)
    assert out["winning_trades"] == 0
    # total_trades is 0 or whatever short entries happened to fire.
    if out["total_trades"] > 0:
        assert out["avg_return"] <= 0


def test_run_metrics_keys_match_db_columns():
    bars = { "T1": _series(120, step=0.5), "T2": _series(120, step=-0.5) }
    out = run(bars)
    assert set(out.keys()) == {
        "hit_rate", "total_trades", "winning_trades", "losing_trades",
        "avg_return", "sharpe", "max_drawdown",
    }
    assert isinstance(out["hit_rate"], float)
    assert isinstance(out["total_trades"], int)
    assert 0.0 <= out["hit_rate"] <= 1.0
