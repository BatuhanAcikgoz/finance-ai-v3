# 12/03 — Correlation Matrix

## Computation

```python
import numpy as np
from sklearn.covariance import LedoitWolf

def compute_correlation(returns: np.ndarray) -> np.ndarray:
    """returns: (T, N) array of daily returns for N holdings.
    Returns (N, N) correlation matrix with Ledoit-Wolf shrinkage."""
    lw = LedoitWolf().fit(returns)
    cov = lw.covariance_
    # Convert covariance to correlation
    d = np.sqrt(np.diag(cov))
    return cov / np.outer(d, d)
```

## Why Shrinkage?

- Sample covariance is unstable when N (holdings) is large relative to T (history)
- Ledoit-Wolf shrinks toward diagonal matrix, improving condition number
- Critical for portfolios with > 30 holdings

## Use Cases

1. **Diversification check:** avg pairwise correlation > 0.7 → flag `low_diversification`
2. **Sector concentration:** cluster analysis on correlation matrix
3. **Stress testing:** shock one holding, compute cascade effect via correlation

## Storage

```sql
CREATE TABLE risk.correlation_matrices (
    portfolio_id UUID,
    as_of_date DATE,
    holdings JSONB,  -- ordered list of tickers
    matrix JSONB,    -- NxN correlation matrix
    method VARCHAR(20) DEFAULT 'ledoit_wolf',
    PRIMARY KEY (portfolio_id, as_of_date)
);
```
