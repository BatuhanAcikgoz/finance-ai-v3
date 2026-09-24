# 06/16 — Report Generation

> **Owner agent:** Report  ·  **Phase:** P2  ·  **SLA:** p50 < 60s · p95 < 3 min

---

## 1. Purpose

Generate morning briefing, evening summary, weekly summary, monthly report emails + dashboard-ready report payloads.

## 2. Trigger

Schedule (morning 08:30, evening 19:00, Friday 19:30, monthly 1st business day)

## 3. Input Schema

Reference: `09-json-schemas/08-decision-record.md + 06-risk-assessment.md`

## 4. Output Schema

Reference: `09-json-schemas/10-report-payload.md`

## 5. Steps

1. Determine report type from trigger.
2. Fetch decisions since last report.
3. Fetch risk assessment.
4. Fetch portfolio state.
5. Call report_agent (LLM):
   - Group decisions by ticker.
   - Generate Turkish narrative for each.
   - Compose executive summary (50 words).
   - Generate action items (top 3).
6. Render HTML email using Jinja2 template (see `15-email-system/01-templates.md`).
7. Render dashboard payload (JSON).
8. Insert into PostgreSQL `reports`.
9. Emit Redis event `report.generated` for notification_dispatch.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| LLM failure                      | Fallback to template-only report (no narrative)     |
| Template render error            | Send plain-text fallback email; alert                |

## 7. n8n Nodes

- `Schedule Trigger` (per schedule)
- `Postgres` (fetch decisions)
- `LLM` (LiteLLM: report agent)
- `Code` (Jinja2 render)
- `Postgres` (insert report)
- `Redis` (publish event)

## 8. Test Cases

1. **Happy path:** Morning briefing → 12 decisions included → email rendered → event emitted.
2. **Edge:** 0 decisions in last 24h → "No actionable items today" email.
3. **Failure:** LLM timeout → fallback template; flag `narrative: false`.

## 9. Idempotency

Key format: `report:{type}:{date_iso}`
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
