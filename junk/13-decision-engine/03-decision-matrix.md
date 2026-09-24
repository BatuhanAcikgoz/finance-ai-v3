# 13/03 — Decision Matrix

## Action Selection

```python
def select_action(weighted_signal: float, confidence: float, 
                  portfolio_context: dict) -> str:
    """Returns: BUY | SELL | HOLD | REDUCE | INSUFFICIENT_EVIDENCE"""
    
    # Insufficient evidence
    if confidence < 0.3:
        return "INSUFFICIENT_EVIDENCE"
    
    # Current exposure
    current_weight = portfolio_context.get("current_weight", 0)
    target_weight = portfolio_context.get("target_weight", 0)
    
    # Signal direction
    if weighted_signal > 0.2:  # bullish threshold
        if current_weight < target_weight * 0.8:
            return "BUY"
        else:
            return "HOLD"
    elif weighted_signal < -0.2:  # bearish threshold
        if current_weight > 0:
            if current_weight > target_weight * 1.5:
                return "REDUCE"
            else:
                return "SELL"
        else:
            return "HOLD"
    else:  # neutral
        return "HOLD"
```

## Decision Matrix Table

| weighted_signal | confidence | current_weight vs target | Action      |
|-----------------|------------|--------------------------|-------------|
| > 0.2           | > 0.7      | < 80% of target          | BUY         |
| > 0.2           | > 0.7      | >= 80% of target         | HOLD        |
| > 0.2           | 0.3 – 0.7  | any                      | HOLD        |
| < -0.2          | > 0.7      | > 150% of target         | REDUCE      |
| < -0.2          | > 0.7      | 0 < weight <= 150%       | SELL        |
| < -0.2          | > 0.7      | 0                        | HOLD        |
| < -0.2          | 0.3 – 0.7  | any                      | HOLD        |
| any             | < 0.3      | any                      | INSUFFICIENT_EVIDENCE |
| -0.2 to 0.2     | any        | any                      | HOLD        |
