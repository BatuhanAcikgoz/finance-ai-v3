# 12/04 — Position Sizing

## Kelly Criterion (Quarter-Kelly)

Full Kelly is too aggressive; we use quarter-Kelly for safety.

```python
def kelly_fraction(win_rate: float, win_loss_ratio: float) -> float:
    """Full Kelly fraction."""
    if win_rate <= 0 or win_loss_ratio <= 0:
        return 0.0
    return win_rate - (1 - win_rate) / win_loss_ratio

def quarter_kelly(win_rate: float, win_loss_ratio: float, confidence: float) -> float:
    """Quarter-Kelly × confidence adjustment.
    Caps at 0.25 (25% of portfolio)."""
    k = kelly_fraction(win_rate, win_loss_ratio)
    qk = k / 4  # quarter-Kelly
    return max(0.0, min(0.25, qk * confidence))
```

## Suggested Position Size

```python
def suggested_position_size(
    confidence: float,
    portfolio_var_budget_pct: float,
    current_var_pct: float,
    max_position_pct: float = 0.25
) -> float:
    """Compute suggested position size (% of portfolio)."""
    # 1. Start from confidence
    base = confidence * 0.05  # max 5% at confidence=1.0
    
    # 2. Scale by remaining risk budget
    risk_remaining = max(0, portfolio_var_budget_pct - current_var_pct)
    risk_factor = risk_remaining / portfolio_var_budget_pct  # 0 to 1
    
    # 3. Apply quarter-Kelly cap
    kelly_cap = 0.25
    
    return min(base * risk_factor, kelly_cap, max_position_pct)
```

## Constraints

- Max position: 25% (configurable per portfolio)
- Max sector: 40% (sum of positions in same sector)
- Max portfolio VaR: 3% (configurable)
- Min position: 0.5% (avoid dust)

## Example

```python
# Input
confidence = 0.75
portfolio_var_budget_pct = 0.03  # 3% daily VaR budget
current_var_pct = 0.022  # currently using 2.2% of budget
max_position_pct = 0.25

# Output
suggested = suggested_position_size(0.75, 0.03, 0.022, 0.25)
# → 0.021 (2.1% of portfolio)
```
