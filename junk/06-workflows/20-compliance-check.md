# 06/20 — Compliance Check

> **Owner agent:** Compliance  ·  **Phase:** P3  ·  **SLA:** p50 < 15s · p95 < 45s

---

## 1. Purpose

Review every decision before delivery: ensure disclaimer present, no investment advice language, evidence citable, RBAC enforced.

## 2. Trigger

Event (`decision.created`)

## 3. Input Schema

Reference: `09-json-schemas/08-decision-record.md`

## 4. Output Schema

Reference: `09-json-schemas/08-decision-record.md (with compliance_status)`

## 5. Steps

1. Receive decision event.
2. Run compliance_agent (LLM):
   - Check for forbidden language ("guaranteed return", "sure thing", "100% certain").
   - Verify disclaimer present.
   - Verify every evidence item has source citation.
   - Check confidence is not overstated.
3. Apply rule-based checks:
   - Disclaimer text present in payload.
   - All evidence[] items have non-null source_url.
   - Confidence in [0, 1].
4. If any check fails → set `compliance_status: BLOCKED` with reason; do NOT dispatch.
5. If all pass → set `compliance_status: APPROVED`; emit Redis event `decision.approved` for notification_dispatch.
6. Insert compliance audit record into `compliance_audits`.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| LLM failure                      | Rule-based checks only; flag `llm_check: false`     |
| False positive (LLM over-strict) | Send to compliance review queue; human review       |

## 7. n8n Nodes

- `Webhook` (trigger from decision_engine)
- `LLM` (LiteLLM: compliance agent)
- `Code` (rule-based checks)
- `Postgres` (update decision + insert audit)
- `Redis` (publish approved event)

## 8. Test Cases

1. **Happy path:** Decision with valid evidence → APPROVED → event emitted.
2. **Failure:** Decision with "guaranteed profit" → BLOCKED; alert compliance team.
3. **Failure:** Missing source_url on evidence → BLOCKED; reason logged.

## 9. Idempotency

Key format: `compliance:{decision_id}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 15s**
- p95 latency: **< 45s**
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
