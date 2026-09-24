# 13/02 — Confidence Scoring

## Formula

```python
def compute_confidence(weighted_signal: float, contradiction_score: float, 
                       evidence_count: int, source_reliability: float,
                       data_freshness: float) -> float:
    """Returns confidence in [0, 1]."""
    
    # Base: absolute weighted signal (magnitude of conviction)
    base = abs(weighted_signal)
    
    # Penalty for contradiction
    contradiction_penalty = contradiction_score * 0.5
    
    # Penalty for insufficient evidence
    evidence_penalty = max(0, (5 - evidence_count) * 0.1)  # 5+ is ideal
    
    # Adjustments
    confidence = base * (1 - contradiction_penalty) * (1 - evidence_penalty)
    confidence *= source_reliability  # 0-1
    confidence *= data_freshness  # 0-1 (1.0 if real-time, 0.5 if stale)
    
    # Cap
    return float(max(0.0, min(1.0, confidence)))
```

## Confidence Buckets

| Bucket      | Range       | Interpretation                          |
|-------------|-------------|-----------------------------------------|
| VERY_LOW    | 0.0 – 0.3   | Insufficient evidence; do not act       |
| LOW         | 0.3 – 0.5   | Monitor only                            |
| MEDIUM      | 0.5 – 0.7   | Optional action; small position         |
| HIGH        | 0.7 – 0.85  | Action recommended; standard size       |
| VERY_HIGH   | 0.85 – 1.0  | Strong action; larger size (still capped)|

## Calibration

Weekly backtest compares predicted confidence vs. actual hit rate per bucket:
- If bucket "0.7-0.8" has actual hit rate 0.65 (predicted 0.75): miscalibration
- Brier score computed across all decisions
- Calibration error > 0.15 → trigger prompt review
