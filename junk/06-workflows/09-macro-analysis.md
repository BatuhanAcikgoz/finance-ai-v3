# 06/09 — Macro Analysis

> **Owner agent:** Macro  ·  **Phase:** P2  ·  **SLA:** p50 < 20s · p95 < 60s

---

## 1. Purpose

On new macro release (TCMB, TÜİK, BDDK), run macro agent: assess impact on rates, FX, equities; produce regime indicator.

## 2. Trigger

Event (`raw.macro.update`)

## 3. Input Schema

Reference: `09-json-schemas/01-market-data.md (macro_indicators)`

## 4. Output Schema

Reference: `09-json-schemas/05-analysis-result.md (MacroAnalysis subtype)`

## 5. Steps

1. Receive macro update event.
2. Fetch latest 12 months of indicators.
3. Call macro_agent (LLM):
   - Assess surprise vs. consensus (using EVDS expectations).
   - Estimate impact on: BIST-100, USD/TRY, 2Y-10Y yield curve, banking sector.
   - Detect regime: BULL, BEAR, RANGE, CRISIS.
4. Insert analysis into PostgreSQL `macro_analyses`.
5. Embed into Qdrant `analysis_memory`.
6. Emit Redis event `analysis.macro.complete`.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| LLM failure                      | INSUFFICIENT_EVIDENCE; supervisor downgrades        |
| Consensus data unavailable       | Skip surprise calc; flag                            |

## 7. n8n Nodes

- `Webhook` (trigger from macro_collector)
- `LLM` (LiteLLM: macro agent)
- `Postgres` (insert + fetch history)
- `Qdrant` (embed)
- `Redis` (publish event)

## 8. Test Cases

1. **Happy path:** TCMB rate decision → impact assessed → regime updated → event emitted.
2. **Edge:** Indicator revision (TÜİK revises CPI) → re-run; flag `revision: true`.
3. **Failure:** LLM timeout → fallback to rule-based regime detection.

## 9. Idempotency

Key format: `macro:{source}:{indicator_code}:{release_date}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 20s**
- p95 latency: **< 60s**
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
