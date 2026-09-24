# 06/02 — Market Collector

> **Owner agent:** —  ·  **Phase:** P1  ·  **SLA:** p50 < 1s per batch · p95 < 5s per batch

---

## 1. Purpose

Ingest BIST tick data, OHLCV bars, and index values in real time during trading hours; end-of-day batch otherwise.

## 2. Trigger

Schedule (every 10 sec during 10:00–18:00 TRT) + webhook (manual replay for backfill)

## 3. Input Schema

Reference: `09-json-schemas/01-market-data.md (input: `{tickers[], effective_at}`)`

## 4. Output Schema

Reference: `09-json-schemas/01-market-data.md (output: tick/bar/index records written to PostgreSQL)`

## 5. Steps

1. Fetch list of active tickers from `tickers` table.
2. For each ticker (parallel, max 50 concurrent):
   a. Call BIST Data Discovery API `/v1/quotes/{ticker}` with `If-Modified-Since` header.
   b. Parse response into `Tick` or `Bar` objects.
   c. Validate against `01-market-data` schema.
   d. Batch insert into PostgreSQL `ticks` (or `bars`) table — COPY for performance.
   e. Update Redis `tick:{ticker}:latest` with last value.
3. Fetch BIST-100 index value, all 14 sector indices.
4. Emit Redis event `raw.market.tick` for downstream consumers (technical_analysis workflow).
5. Emit WebSocket broadcast `market.update` for dashboard clients.
6. On schema validation failure → route to DLQ + alert.

## 6. Error Handling

| Failure                       | Mitigation                                          |
|-------------------------------|-----------------------------------------------------|
| BIST API 5xx                  | Retry 3× exponential backoff (1s, 4s, 16s); fallback to websocket |
| BIST API 429 (rate limit)     | Backoff per `Retry-After` header; alert if queue > 1000 |
| BIST API 4xx (auth)           | Alert immediately; do NOT retry                     |
| Schema validation failure     | Write raw payload to `ticks_invalid` table; alert   |
| PostgreSQL write timeout      | Buffer in Redis stream; replay after recovery       |
| Redis write failure           | Continue (PostgreSQL is source of truth); alert     |

## 7. n8n Nodes

- `Schedule Trigger` (every 10 sec, 10:00–18:00 TRT weekdays)
- `HTTP Request` (BIST API)
- `Code` (Python: parse + validate + transform)
- `Postgres` (COPY insert)
- `Redis` (SET latest + PUBLISH event)
- `WebSocket Client` (broadcast to dashboard)
- `Error Trigger` (DLQ + alert)

## 8. Test Cases

1. **Happy path:** 10 tickers requested → 10 ticks inserted, 10 Redis keys updated, 1 event emitted.
2. **Edge:** Market closed → 0 ticks returned; workflow exits cleanly with `data_completeness: "market_closed"`.
3. **Edge:** Ticker suspended (e.g. delisted) → 404 from API; ticker flagged `inactive` in DB; not requested again.
4. **Failure:** BIST API 503 → retry succeeds on 2nd attempt; if all 3 fail → alert + DLQ.
5. **Failure:** Schema mismatch (new field in BIST response) → route to `ticks_invalid`; alert.

## 9. Idempotency

Key format: `market:{ticker}:{effective_at_iso_minute}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 1s per batch**
- p95 latency: **< 5s per batch**
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
