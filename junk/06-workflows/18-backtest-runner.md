# 06/18 — Backtest Runner

> **Owner agent:** Backtest  ·  **Phase:** P3  ·  **SLA:** p50 < 5 min · p95 < 15 min

---

## 1. Purpose

Weekly: replay past decisions against realized outcomes; compute hit-rate, calibration, attribution; propose weight recalibration.

## 2. Trigger

Schedule (Monday 06:00 TRT)

## 3. Input Schema

Reference: `09-json-schemas/08-decision-record.md + 01-market-data.md`

## 4. Output Schema

Reference: `09-json-schemas/10-report-payload.md (BacktestReport subtype)`

## 5. Steps

1. Fetch decisions from last 4 weeks.
2. For each decision, fetch realized outcome (price change over horizon).
3. Compute:
   - Hit rate (% of decisions where direction was correct).
   - Calibration (confidence vs. actual probability).
   - Attribution (which streams contributed most to correct decisions).
4. Call backtest_agent (LLM):
   - Identify patterns in wrong decisions.
   - Propose weight adjustments for each evidence stream.
5. Insert backtest report into PostgreSQL `backtests`.
6. Emit Redis event `backtest.complete`.
7. Weight adjustments require manual approval (dashboard button).

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| Price history missing            | Skip decision in backtest; flag                      |
| LLM failure                      | Statistical report only                             |

## 7. n8n Nodes

- `Schedule Trigger` (Mon 06:00)
- `Postgres` (fetch decisions + prices)
- `Code` (numpy: hit rate, calibration)
- `LLM` (LiteLLM: backtest agent)
- `Postgres` (insert report)
- `Redis` (publish event)

## 8. Test Cases

1. **Happy path:** 50 decisions backtested → hit rate 62%, calibration 0.83.
2. **Edge:** 0 decisions in 4 weeks → empty backtest report.
3. **Failure:** Price data gap → affected decisions excluded; flag.

## 9. Idempotency

Key format: `backtest:{week_iso}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 5 min**
- p95 latency: **< 15 min**
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
