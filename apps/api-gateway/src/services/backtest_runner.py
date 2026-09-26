"""Pure-math backtest runner (issue #3 / FR-072..FR-074).

Strategy: SMA20 vs SMA50 crossover. For each ticker, walk forward day-by-day:
  - At each bar with at least 50 prior closes, compute sma20 and sma50.
  - If close > sma20 > sma50 -> enter at next bar's open.
  - If close < sma20 < sma50 -> exit at next bar's close (close the position).
  - Hold for up to ``exit_after_bars`` bars (default 5).
  - Trade return = (exit_price - entry_price) / entry_price.

Aggregates across the universe to compute:
  hit_rate, total_trades, winning_trades, losing_trades,
  avg_return, sharpe, max_drawdown.

No LLM, no external IO. Asyncpg is the only dep. The runner returns the
metrics dict; the caller persists into ``analysis.backtest_runs``.
"""
from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger(__name__)


@dataclass
class _Bar:
    """Minimal bar shape we need."""
    close: float
    open: float


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window or window <= 0:
        return None
    return sum(values[-window:]) / window


def run(
    bars_by_ticker: dict[str, list[_Bar]],
    exit_after_bars: int = 5,
) -> dict:
    """Run the SMA20/50 crossover backtest over the given bars.

    Returns the metrics dict (also shape-compatible with
    analysis.backtest_runs columns).
    """
    trade_returns: list[float] = []

    for ticker, bars in bars_by_ticker.items():
        closes = [b.close for b in bars]
        in_position = False
        entry_idx = -1

        for i in range(50, len(bars)):
            sma20 = _sma(closes[:i], 20)
            sma50 = _sma(closes[:i], 50)
            if sma20 is None or sma50 is None:
                continue

            last_close = closes[i]
            uptrend = last_close > sma20 > sma50
            downtrend = last_close < sma20 < sma50

            if not in_position and uptrend and i + 1 < len(bars):
                # Enter long at next bar's open.
                in_position = True
                entry_idx = i + 1
                continue

            if in_position:
                age = i - entry_idx
                if downtrend or age >= exit_after_bars:
                    # Exit at this bar's close (we already have it).
                    entry_price = bars[entry_idx].open
                    exit_price = bars[i].close
                    if entry_price > 0:
                        ret = (exit_price - entry_price) / entry_price
                        trade_returns.append(ret)
                    in_position = False

    if not trade_returns:
        return {
            "hit_rate": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "avg_return": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
        }

    total = len(trade_returns)
    winners = sum(1 for r in trade_returns if r > 0)
    losers = sum(1 for r in trade_returns if r <= 0)
    avg = sum(trade_returns) / total
    try:
        sharpe = (statistics.mean(trade_returns) / statistics.stdev(trade_returns)) \
                 * math.sqrt(252) if len(trade_returns) > 1 else 0.0
    except statistics.StatisticsError:
        sharpe = 0.0

    # Max drawdown of the equity curve (cumulative product of 1 + r).
    equity = [1.0]
    for r in trade_returns:
        equity.append(equity[-1] * (1.0 + r))
    peaks = []
    peak = equity[0]
    for v in equity:
        peak = max(peak, v)
        peaks.append(peak)
    drawdowns = [(e - p) / p if p > 0 else 0.0 for e, p in zip(equity, peaks)]
    max_dd = min(drawdowns) if drawdowns else 0.0

    return {
        "hit_rate": winners / total,
        "total_trades": total,
        "winning_trades": winners,
        "losing_trades": losers,
        "avg_return": avg,
        "sharpe": float(sharpe),
        "max_drawdown": float(max_dd),
    }


__all__ = ["run", "_Bar"]
