# 12/01 — Risk Metrics Definitions

## VaR (Value at Risk)

**1-day 95% VaR** = the loss that will not be exceeded with 95% probability over 1 day.

**Computation (historical simulation):**
```python
import numpy as np

def compute_var(returns: np.ndarray, alpha: float = 0.95) -> float:
    """returns: array of historical daily portfolio returns (last 252 days).
    Returns VaR as a negative number (loss)."""
    return float(np.percentile(returns, (1 - alpha) * 100))

# Usage:
# returns = portfolio_daily_returns last 252 days
# var = compute_var(returns, 0.95)
# If var = -0.023, means: 95% chance loss < 2.3% tomorrow
```

## CVaR (Conditional VaR / Expected Shortfall)

**1-day 95% CVaR** = expected loss given that the loss exceeds VaR.

```python
def compute_cvar(returns: np.ndarray, alpha: float = 0.95) -> float:
    var = compute_var(returns, alpha)
    tail = returns[returns <= var]
    return float(tail.mean()) if len(tail) > 0 else var
```

## Beta

```python
def compute_beta(port_returns: np.ndarray, bench_returns: np.ndarray) -> float:
    cov = np.cov(port_returns, bench_returns)
    return float(cov[0, 1] / cov[1, 1])
```

## Tracking Error

```python
def compute_tracking_error(port_returns: np.ndarray, bench_returns: np.ndarray) -> float:
    excess = port_returns - bench_returns
    return float(excess.std())
```

## HHI (Herfindahl-Hirschman Index)

```python
def compute_hhi(weights: np.ndarray) -> float:
    """weights: array of position weights, sum to 1.
    Returns HHI in [1/N, 1.0]. Higher = more concentrated."""
    return float((weights ** 2).sum())
```

## Sharpe Ratio

```python
def compute_sharpe(returns: np.ndarray, rf: float = 0.0, periods: int = 252) -> float:
    excess = returns - rf / periods
    return float(np.sqrt(periods) * excess.mean() / excess.std())
```

## Sortino Ratio

```python
def compute_sortino(returns: np.ndarray, rf: float = 0.0, periods: int = 252) -> float:
    excess = returns - rf / periods
    downside = excess[excess < 0]
    return float(np.sqrt(periods) * excess.mean() / downside.std())
```
