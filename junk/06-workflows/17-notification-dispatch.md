# 06/17 — Notification Dispatch

> **Owner agent:** —  ·  **Phase:** P2  ·  **SLA:** p50 < 30s · p95 < 60s

---

## 1. Purpose

Route alerts and reports to channels (email, Slack, dashboard push) with deduplication and rate limiting.

## 2. Trigger

Event (`decision.created`, `report.generated`, `alert.*`)

## 3. Input Schema

Reference: `09-json-schemas/09-alert-event.md + 10-report-payload.md`

## 4. Output Schema

Reference: `09-json-schemas/N/A — side-effect: sends email/Slack/WS`

## 5. Steps

1. Receive event.
2. Compute dedup hash (event type + ticker + window).
3. Check Redis `notif:dedup:{hash}` — skip if exists within 60min window.
4. Apply rate limit: max 5 CRITICAL per ticker per day.
5. Route to channels per user preferences:
   - Email (SendGrid)
   - Slack webhook (CRITICAL + EMERGENCY only)
   - Dashboard WebSocket push
6. Set Redis dedup key with 60min TTL.
7. Log delivery in PostgreSQL `notification_deliveries`.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| SendGrid 5xx                     | Retry 3× backoff; queue in Redis; alert             |
| Slack webhook 4xx                | Log; do NOT retry                                   |
| WebSocket client disconnected    | Skip WS push; email still sent                      |

## 7. n8n Nodes

- `Webhook` (trigger from any source)
- `Code` (dedup + rate limit)
- `HTTP Request` (SendGrid)
- `HTTP Request` (Slack webhook)
- `WebSocket Client` (dashboard push)
- `Postgres` (insert delivery log)

## 8. Test Cases

1. **Happy path:** CRITICAL alert → email + Slack + WS push within 30s.
2. **Edge:** Same alert twice in 5 min → second suppressed by dedup.
3. **Failure:** SendGrid down → queue in Redis; retry 5 min; alert.

## 9. Idempotency

Key format: `notif:{event_type}:{ticker}:{window_start_iso}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 30s**
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
