# 06/12 — Sector Analysis

> **Owner agent:** Sector  ·  **Phase:** P2  ·  **SLA:** p50 < 60s · p95 < 3 min

---

## 1. Purpose

Daily at 18:30 TRT, score all 14 BIST sectors on momentum, breadth, and relative strength; compute cross-sector correlation matrix weekly.

## 2. Trigger

Schedule (daily 18:30 TRT, plus weekly Mon 09:00 for correlation)

## 3. Input Schema

Reference: `09-json-schemas/01-market-data.md (sector indices)`

## 4. Output Schema

Reference: `09-json-schemas/05-analysis-result.md (SectorAnalysis subtype)`

## 5. Steps

1. Fetch 14 sector index values for last 250 trading days.
2. Compute per-sector:
   - 1d / 1w / 1m / 3m / YTD returns
   - Breadth (% of constituents above SMA50)
   - Relative strength vs. BIST-100
3. Call sector_agent (LLM) to interpret: leader/laggard rotation signals.
4. On Mondays: compute 90-day correlation matrix → insert into `sector_correlations`.
5. Insert daily sector scores into `sector_analyses`.
6. Emit Redis event `analysis.sector.complete`.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| Sector index missing             | Skip; flag                                          |
| LLM failure                      | Rule-based interpretation only                      |

## 7. n8n Nodes

- `Schedule Trigger` (daily 18:30)
- `Code` (pandas: returns, breadth, correlation)
- `LLM` (LiteLLM: sector agent)
- `Postgres` (insert)
- `Redis` (publish event)

## 8. Test Cases

1. **Happy path:** 14 sectors scored → 1 event emitted.
2. **Edge:** New sector index added → automatically included next run.
3. **Failure:** pandas exception → alert; fallback to numpy direct computation.

## 9. Idempotency

Key format: `sector:{date_iso}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 60s**
- p95 latency: **< 3 min**
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
