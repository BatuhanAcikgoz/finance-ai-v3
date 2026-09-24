# 06/06 — Macro Collector

> **Owner agent:** Macro  ·  **Phase:** P1  ·  **SLA:** p50 < 2 min · p95 < 5 min

---

## 1. Purpose

Daily collection of TCMB EVDS indicators, monthly TÜİK releases, and weekly BDDK bulletins.

## 2. Trigger

Schedule (daily 11:00 TRT, plus event-driven on TÜİK press release days)

## 3. Input Schema

Reference: `09-json-schemas/N/A — fixed source list`

## 4. Output Schema

Reference: `09-json-schemas/01-market-data.md (macro_indicators subtype)`

## 5. Steps

1. TCMB EVDS API:
   - Fetch series: TP_FAO, TP_FAO01, TP_AB, TP_KM10, TP_KM11, TP_KM12, etc. (policy rate, FX reserves, money supply).
   - Insert into PostgreSQL `macro_indicators` with `source: TCMB`.
2. TÜİK API:
   - Fetch latest CPI, PPI, unemployment, GDP from open data portal.
   - Insert into PostgreSQL `macro_indicators` with `source: TUIKS`.
3. BDDK bulletin (weekly PDF):
   - Download PDF from bddk.org.tr.
   - Extract tables with `pdfplumber`.
   - Parse sector NPL, capital adequacy, total deposits.
   - Insert into PostgreSQL `macro_indicators` with `source: BDDK`.
4. Emit Redis event `raw.macro.update` for macro_analysis workflow.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| TCMB EVDS API down               | Retry 3× backoff; alert; use last known values      |
| TÜİK release delayed             | Calendar-aware; retry at 12:00, 14:00               |
| BDDK PDF structure changed       | Parse error → alert; do NOT silent skip             |
| Indicator value out of expected range | Sanity check vs. last value; flag anomaly      |

## 7. n8n Nodes

- `Schedule Trigger` (daily 11:00 TRT)
- `HTTP Request` (TCMB + TÜİK)
- `HTTP Request` (BDDK PDF download)
- `Code` (pdfplumber extraction)
- `Postgres` (insert indicators)
- `Redis` (publish event)

## 8. Test Cases

1. **Happy path:** All 3 sources fetched → 25 indicators inserted, 1 event emitted.
2. **Edge:** TÜİK release delayed → workflow logs `pending: TUIKS`; retry at 12:00.
3. **Failure:** TCMB API key expired → 401; alert immediately; no retry.

## 9. Idempotency

Key format: `macro:{source}:{indicator_code}:{date_iso}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 2 min**
- p95 latency: **< 5 min**
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
