# 06/01 — Scheduler

> **Owner agent:** (infra)  ·  **Phase:** P1  ·  **SLA:** p50 < 1s · p95 < 5s

---

## 1. Purpose

Master scheduler that triggers all other workflows on their respective schedules. Implemented as n8n cron nodes; no business logic.

## 2. Trigger

Schedule (cron). See schedule table below.

| Time (TRT)      | Workflow triggered |
|------------------|--------------------|
| Every weekday 09:45 | market_collector (pre-open) |
| Every 10 sec during trading (10:00–18:00) | market_collector (tick) |
| Every 5 min, 24/7 | kap_collector |
| Every 2 min, 24/7 | news_collector |
| Daily 18:30 | tefas_collector |
| Daily 11:00 | macro_collector |
| Daily 18:30 | sector_analysis |
| Daily 19:00 | report_generation (evening) |
| Weekday 08:30 | report_generation (morning) |
| Friday 19:30 | report_generation (weekly) |
| 1st business day 09:00 | report_generation (monthly) |
| Monday 06:00 | backtest_runner |

## 3. Input Schema

Reference: `09-json-schemas/N/A (no input — pure scheduler)`

## 4. Output Schema

Reference: `09-json-schemas/N/A (sends trigger events only)`

## 5. Steps

1. Cron node fires at scheduled time.
2. For each target workflow, emit a Redis message on `trigger.{workflow_name}` channel with payload `{triggered_at, effective_at}`.
3. Log emit to `workflow_triggers` table for auditability.

## 6. Error Handling

| Failure               | Mitigation                                          |
|-----------------------|-----------------------------------------------------|
| n8n process down      | systemd auto-restart; missing triggers detected by monitoring alert |
| Redis down            | Retry 3× exponential backoff; alert if still failing |
| Misfire (skipped run) | Detected by `workflow_trigger_gap` metric           |

## 7. n8n Nodes

- `Cron` (trigger) — one node per schedule entry
- `Redis` (publish) — emits trigger messages
- `Postgres` (insert) — audit log

## 8. Test Cases

1. **Happy path:** Trigger at 09:45 TRT → market_collector receives trigger within 1s.
2. **Edge:** Trading day that opens late (e.g. holiday) → trigger suppressed by trading calendar check.
3. **Failure:** Redis unavailable → retry 3× then alert; trigger logged in DLQ.

## 9. Idempotency

Key format: `scheduler:{workflow}:{scheduled_time_iso}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 1s**
- p95 latency: **< 5s**
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
