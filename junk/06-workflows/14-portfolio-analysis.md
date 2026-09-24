# 06/14 — Portfolio Analysis

> **Owner agent:** Portfolio  ·  **Phase:** P2  ·  **SLA:** p50 < 5s · p95 < 15s

---

## 1. Purpose

On every decision record, apply portfolio context: compute exposure impact, position sizing, drift from target.

## 2. Trigger

Event (`analysis.*.complete` aggregated by supervisor)

## 3. Input Schema

Reference: `09-json-schemas/07-portfolio-state.md + 08-decision-record.md (draft)`

## 4. Output Schema

Reference: `09-json-schemas/08-decision-record.md (with portfolio_context)`

## 5. Steps

1. Receive draft decision record.
2. Fetch portfolio state (holdings, target weights, risk budget).
3. Compute:
   - Current exposure to ticker
   - Post-trade exposure (if action executed)
   - Position size suggestion (Kelly fraction × confidence × risk budget)
   - Drift from target weights
4. Enrich decision record with portfolio_context.
5. Emit Redis event `analysis.portfolio.complete`.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| Portfolio not found              | Skip; flag `portfolio_id: null`                     |
| Negative Kelly (edge negative)   | Skip recommendation; flag                            |

## 7. n8n Nodes

- `Webhook` (trigger from supervisor)
- `Code` (pandas: exposure, Kelly)
- `Postgres` (update decision record)
- `Redis` (publish event)

## 8. Test Cases

1. **Happy path:** BUY recommendation on THYAO → position size = 2.5% of portfolio.
2. **Edge:** Ticker already at 10% weight → position size = 0 (drift cap).
3. **Failure:** Kelly formula returns NaN → flag, default to 1% fixed size.

## 9. Idempotency

Key format: `portfolio:{portfolio_id}:{decision_id}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 5s**
- p95 latency: **< 15s**
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
