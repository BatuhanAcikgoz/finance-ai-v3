# 06/04 — Tefas Collector

> **Owner agent:** —  ·  **Phase:** P1  ·  **SLA:** p50 < 10 min for full batch · p95 < 20 min

---

## 1. Purpose

Daily scrape of TEFAS for fund NAVs, flows, and metadata for all public funds (mutual, participation, gold, index, bond).

## 2. Trigger

Schedule (daily 18:30 TRT, after BIST close)

## 3. Input Schema

Reference: `09-json-schemas/04-tefas-fund.md (input: `{date}`)`

## 4. Output Schema

Reference: `09-json-schemas/04-tefas-fund.md (output: fund NAV + flow records)`

## 5. Steps

1. Fetch list of active fund codes from `tefas_funds` table.
2. For each fund (parallel, max 20 concurrent):
   a. HTTP GET `https://www.tefas.gov.tr/FonAnaliz.aspx` with params `{FundCode, Date}`.
   b. Parse HTML with BeautifulSoup — extract NAV, return YTD, daily flow (subscription/redemption).
   c. Validate against `04-tefas-fund` schema.
   d. Insert into PostgreSQL `tefas_navs` and `tefas_flows` tables.
3. Detect new funds (code not in DB) → insert into `tefas_funds` with `discovered_at`.
4. Detect delisted funds (404) → flag `active: false`.
5. Emit Redis event `raw.tefas.daily` for downstream consumers.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| TEFAS HTML structure changed     | Parse error → alert; do NOT silent skip             |
| 429 (rate limit)                 | Backoff per `Retry-After`; throttle to 5 req/sec    |
| NAV value not parseable          | Insert with `nav: null`, `data_completeness: "partial"` |
| Fund code 404                    | Flag `active: false` in DB                          |

## 7. n8n Nodes

- `Schedule Trigger` (daily 18:30 TRT)
- `HTTP Request` (TEFAS)
- `HTML Extract` (BeautifulSoup via Python code node)
- `Postgres` (insert NAVs + flows)
- `Redis` (publish event)

## 8. Test Cases

1. **Happy path:** 800 funds scraped → 800 NAV rows + 800 flow rows; 1 event emitted.
2. **Edge:** TEFAS site maintenance → all 800 fail → alert; retry 1 hour later.
3. **Edge:** New fund code discovered → inserted into `tefas_funds`; logged.
4. **Failure:** NAV field missing in HTML → row inserted with `nav: null`, alert with sample.

## 9. Idempotency

Key format: `tefas:{fund_code}:{date_iso}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 10 min for full batch**
- p95 latency: **< 20 min**
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
