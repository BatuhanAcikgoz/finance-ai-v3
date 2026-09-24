# 13/01 — Evidence Aggregation

## Input

8 streams, each producing `{signal, strength, confidence, source_id}`:
- TECHNICAL
- FUNDAMENTAL
- MACRO
- NEWS
- SENTIMENT
- SECTOR
- PORTFOLIO (existing exposure)
- SIMILARITY (historical analogs from Qdrant)

## Weighted Aggregation

```python
def aggregate_evidence(evidence: list, weights: dict) -> dict:
    """evidence: list of {stream, signal, strength, confidence, ...}
    weights: {stream: weight} (sums to 1.0)
    Returns: {weighted_signal, evidence_count, contradiction_score}"""
    
    if len(evidence) < 3:
        return {"weighted_signal": 0, "evidence_count": len(evidence), "contradiction_score": 0, "insufficient": True}
    
    # Convert signals to numeric: BULLISH=+1, NEUTRAL=0, BEARISH=-1
    signal_map = {"BULLISH": 1, "NEUTRAL": 0, "BEARISH": -1}
    
    # Weighted signal
    weighted_signal = 0
    total_weight_used = 0
    for e in evidence:
        w = weights.get(e["stream"], 0)
        s = signal_map[e["signal"]] * e["strength"] * e["confidence"]
        weighted_signal += w * s
        total_weight_used += w
    
    if total_weight_used > 0:
        weighted_signal /= total_weight_used  # normalize
    
    # Contradiction score = variance of normalized signals
    signals = [signal_map[e["signal"]] * e["strength"] for e in evidence]
    contradiction_score = float(np.var(signals)) if len(signals) > 1 else 0
    
    return {
        "weighted_signal": float(weighted_signal),
        "evidence_count": len(evidence),
        "contradiction_score": float(contradiction_score),
        "insufficient": False
    }
```

## Default Weights (v1)

```python
DEFAULT_WEIGHTS = {
    "TECHNICAL": 0.15,
    "FUNDAMENTAL": 0.20,
    "MACRO": 0.10,
    "NEWS": 0.10,
    "SENTIMENT": 0.10,
    "SECTOR": 0.10,
    "PORTFOLIO": 0.10,
    "SIMILARITY": 0.15,
}
# Sum = 1.00
```

Weights are versioned in `decision_weights` table. Backtest agent proposes adjustments; require human approval.
