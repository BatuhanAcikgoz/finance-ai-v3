# 13 — Decision Engine Overview

> Aggregates evidence from 8 streams into a single decision record with confidence, action, and traceability.

## Decision Flow (recap)

```
8 evidence streams → weighted aggregation → confidence scoring →
portfolio filter → decision matrix → compliance check → notification
```

## Key Properties

1. **Multi-evidence:** requires ≥ 3 streams
2. **Weighted:** weights learned from backtest
3. **Portfolio-aware:** respects constraints
4. **Explainable:** every decision has full evidence trace
5. **Auditable:** 2-year retention
6. **Versioned:** weights + prompt versions stored with every decision
