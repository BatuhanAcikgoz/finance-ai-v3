# 06/03 — Kap Collector

> **Owner agent:** Fundamental  ·  **Phase:** P1  ·  **SLA:** p50 < 30s per batch · p95 < 2 min per batch

---

## 1. Purpose

Poll KAP REST API every 5 minutes for new disclosures, classify them, embed them in Qdrant, and dispatch material ones to the fundamental_analysis workflow.

## 2. Trigger

Schedule (every 5 min, 24/7)

## 3. Input Schema

Reference: `09-json-schemas/03-kap-announcement.md (input: `{since, max_results}`)`

## 4. Output Schema

Reference: `09-json-schemas/03-kap-announcement.md (output: classified KAP disclosure records)`

## 5. Steps

1. Query KAP API `/api/v1/disclosures?since={last_poll_time}`.
2. For each new disclosure:
   a. Fetch full text from `/api/v1/disclosures/{id}`.
   b. Parse into `KapAnnouncement` schema fields (title, summary, body, category_hint, related_tickers).
   c. Classify category with LLM (one of 14 official KAP categories) — see `08-prompts/03-fundamental-prompt.md`.
   d. Detect materiality (boolean) using rule + LLM hybrid.
   e. Extract tickers mentioned (regex + LLM verification).
   f. Embed body+summary into Qdrant collection `kap_embeddings`.
   g. Insert into PostgreSQL `kap_disclosures` table.
   h. If material AND affects portfolio holdings → emit event `raw.kap.material` for fundamental_analysis.
3. Update `kap_last_poll_at` in Redis.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| KAP API 5xx                      | Retry 3× backoff (5s, 25s, 125s); alert if all fail |
| KAP API 4xx                      | Alert immediately; do NOT retry                     |
| LLM classification failure       | Default category `OTHER`; flag `needs_review: true` |
| Qdrant unavailable               | Skip embedding; flag `embedded: false`; retry queue |
| Duplicate detection              | Hash on (publishing_id, version); skip if exists    |

## 7. n8n Nodes

- `Schedule Trigger` (every 5 min)
- `HTTP Request` (KAP API)
- `LLM` (LiteLLM: classify + materiality + ticker extraction)
- `Qdrant` (insert embedding)
- `Postgres` (insert disclosure)
- `Redis` (publish material event)
- `Error Trigger` (DLQ + alert)

## 8. Test Cases

1. **Happy path:** 3 new disclosures → 3 classified, 3 embedded, 1 flagged material → event emitted.
2. **Edge:** No new disclosures since last poll → workflow exits cleanly in < 5s.
3. **Edge:** Disclosure with no related tickers → `related_tickers: []`, not flagged material.
4. **Failure:** LLM returns invalid JSON → repair attempt; if 2nd failure → category `OTHER`, `needs_review: true`.
5. **Failure:** Qdrant timeout → embedding skipped, `embedded: false`; retry workflow picks up later.

## 9. Idempotency

Key format: `kap:{publishing_id}:{version}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 30s per batch**
- p95 latency: **< 2 min per batch**
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
