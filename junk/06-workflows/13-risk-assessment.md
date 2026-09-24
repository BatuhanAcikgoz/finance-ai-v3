# 06/13 — Risk Assessment

> **Owner agent:** Risk  ·  **Phase:** P2  ·  **SLA:** p50 < 30s · p95 < 90s

---

## 1. Purpose

Daily (and on portfolio change) compute risk metrics for every portfolio: VaR, CVaR, beta, concentration, factor exposures.

## 2. Trigger

Schedule (daily 18:45 TRT) + event (`raw.portfolio.change`)

## 3. Input Schema

Reference: `09-json-schemas/07-portfolio-state.md`

## 4. Output Schema

Reference: `09-json-schemas/06-risk-assessment.md`

## 5. Steps

1. Fetch portfolio holdings + weights.
2. Fetch 1-year price history for all holdings + BIST-100 benchmark.
3. Compute:
   - 1-day 95% VaR (historical simulation)
   - 1-day 95% CVaR
   - Beta to BIST-100
   - Tracking error
   - HHI concentration
   - Sector exposure
   - Style exposure (value/growth/quality using BIST style indices)
4. Insert into PostgreSQL `risk_assessments`.
5. If VaR > portfolio risk budget → emit `alert.risk.exceeded`.
6. Emit Redis event `analysis.risk.complete`.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| Price history insufficient       | Use shorter window; flag `window: 180d`             |
| Singular covariance matrix       | Use shrinkage estimator (Ledoit-Wolf)               |

## 7. n8n Nodes

- `Schedule Trigger` (daily 18:45)
- `Code` (numpy/pandas: VaR, CVaR, beta)
- `Postgres` (insert)
- `Redis` (publish event + alert)

## 8. Test Cases

1. **Happy path:** 12 holdings → VaR=2.3%, beta=0.95, HHI=0.18.
2. **Edge:** Single-holding portfolio → VaR = holding volatility; HHI=1.0; concentration alert.
3. **Failure:** numpy LinAlgError → shrinkage estimator fallback.

## 9. Idempotency

Key format: `risk:{portfolio_id}:{date_iso}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 30s**
- p95 latency: **< 90s**
- Failure rate target: **< 1%**

## 11. Observability

- Every step emits OpenTelemetry span with `workflow_id`, `step_id`, `idempotency_key`.
- Workflow-level metrics: `workflow_duration_seconds`, `workflow_step_failures_total`, `workflow_retries_total`.
- All logs JSON-structured, `workflow_id` as correlation field.

## 12. Dependencies

- Upstream: see trigger
- Downstream: see output schema consumers
- External APIs: see step list
- LLM calls: via LiteLLM only (never direct SDK)
