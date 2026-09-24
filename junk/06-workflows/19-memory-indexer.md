# 06/19 — Memory Indexer

> **Owner agent:** Memory  ·  **Phase:** P2  ·  **SLA:** p50 < 2s · p95 < 8s

---

## 1. Purpose

Embed every analysis result, KAP disclosure, news article, and decision record into Qdrant for historical similarity search.

## 2. Trigger

Event (`analysis.*.complete`, `decision.created`)

## 3. Input Schema

Reference: `09-json-schemas/All analysis result schemas`

## 4. Output Schema

Reference: `09-json-schemas/N/A — side-effect: writes to Qdrant`

## 5. Steps

1. Receive event.
2. Fetch full record from PostgreSQL.
3. Build text representation (title + summary + key fields).
4. Call embedding API (via LiteLLM: `text-embedding-3-large` or local model).
5. Insert into Qdrant collection based on event type:
   - `analysis.technical` → `analysis_memory`
   - `analysis.fundamental` → `analysis_memory`
   - `analysis.macro` → `analysis_memory`
   - `analysis.news` → `news_embeddings`
   - `raw.kap.material` → `kap_embeddings`
   - `decision.created` → `decision_memory`
6. Store with payload: `{type, ticker, date, source_id}`.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| Embedding API failure            | Retry 3×; queue in Redis                            |
| Qdrant unavailable               | Skip; flag `embedded: false`; retry queue           |

## 7. n8n Nodes

- `Webhook` (trigger from any analysis workflow)
- `Postgres` (fetch full record)
- `LLM` (LiteLLM: embedding)
- `Qdrant` (insert)

## 8. Test Cases

1. **Happy path:** Decision record → embedded in 1.5s.
2. **Edge:** Text > 8K tokens → chunked embedding; multiple vectors per record.
3. **Failure:** Qdrant timeout → retry queue; `embedded: false` flag.

## 9. Idempotency

Key format: `memory:{record_type}:{record_id}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 2s**
- p95 latency: **< 8s**
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
