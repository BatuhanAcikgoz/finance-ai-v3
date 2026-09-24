# 12/02 — VaR Model Specification

## Methodology: Historical Simulation

**Why historical (not parametric or Monte Carlo)?**
- Non-parametric: no assumption of normal returns (BIST returns are fat-tailed)
- Robust to outliers
- Easy to explain to compliance
- Industry standard for institutional portfolios

## Window

- **Default:** 252 trading days (1 year)
- **Fallback (if < 252 days history):** minimum 60 days, flag `window_short: true`
- **Cold start (< 60 days):** use BIST-100 returns as proxy, flag `proxy: true`

## Confidence Levels

- **95%** for daily reporting (standard)
- **99%** for compliance (regulatory)
- Both computed and stored

## Backtesting VaR

Daily backtest: did actual loss exceed VaR?
- Expected breaches: 5% of days (for 95% VaR)
- Kupiec test: if breach rate significantly different from 5%, model needs review

```python
def kupiec_test(breaches: int, total: int, alpha: float = 0.95) -> float:
    """Returns p-value. If < 0.05, model is miscalibrated."""
    expected = total * (1 - alpha)
    # Likelihood ratio test
    # ... (full implementation in services/risk_engine/src/kupiec.py)
```

## Limits

| Limit                    | Action                                    |
|--------------------------|-------------------------------------------|
| VaR > 3% (daily)         | WARN alert                                |
| VaR > 5% (daily)         | CRITICAL alert + suggest rebalance        |
| VaR > risk_budget_pct    | BLOCK new BUY decisions                   |
| CVaR > 1.5 × VaR         | Tail risk warning                         |
| Breach rate > 8% (Kupiec)| Recalibrate model                         |
