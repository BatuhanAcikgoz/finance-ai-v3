# 06/15 — Decision Engine

> **Owner agent:** Supervisor  ·  **Phase:** P2  ·  **SLA:** p50 < 5s · p95 < 20s

---

## 1. Purpose

Aggregate evidence from 8 streams, compute weighted confidence, apply decision matrix, emit decision record.

## 2. Trigger

Event (`analysis.portfolio.complete` — i.e. all upstream done)

## 3. Input Schema

Reference: `09-json-schemas/05-analysis-result.md (all subtypes)`

## 4. Output Schema

Reference: `09-json-schemas/08-decision-record.md`

## 5. Steps

1. Receive aggregated evidence pack from supervisor.
2. For each evidence item, extract `{stream, signal, strength, confidence}`.
3. Apply decision matrix:
   - Weight each stream (weights from `decision_weights` table, versioned).
   - Compute weighted_signal = Σ(weight × signal × confidence).
   - Compute evidence_count (≥ 3 required, see §2.4 master prompt).
   - Compute contradiction_score (variance of normalized signals).
   - Compute confidence = weighted_signal × (1 - contradiction_score).
4. Apply portfolio constraints (max position, max sector exposure).
5. Determine action: BUY / SELL / HOLD / REDUCE / INSUFFICIENT_EVIDENCE.
6. Compute position sizing (Kelly fraction × confidence × risk budget).
7. Insert decision record with full evidence[] array.
8. Emit Redis event `decision.created`.
9. Trigger compliance_check workflow.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| < 3 evidence streams             | INSUFFICIENT_EVIDENCE; supervisor downgrades        |
| Contradiction score > 0.6        | Confidence capped at 0.4; flag                      |
| Weights table corrupted          | Fallback to default weights; alert                  |

## 7. n8n Nodes

- `Webhook` (trigger from supervisor)
- `Code` (numpy: weighted aggregation, Kelly)
- `Postgres` (insert decision record)
- `Redis` (publish event + trigger compliance)

## 8. Test Cases

1. **Happy path:** 5 streams agree on BUY → confidence 0.78 → action BUY.
2. **Edge:** 3 streams BUY, 2 streams SELL → contradiction_score 0.55 → confidence capped 0.4 → action HOLD.
3. **Failure:** Only 2 streams available → INSUFFICIENT_EVIDENCE.

## 9. Idempotency

Key format: `decision:{portfolio_id}:{ticker}:{effective_at_iso}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 5s**
- p95 latency: **< 20s**
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
