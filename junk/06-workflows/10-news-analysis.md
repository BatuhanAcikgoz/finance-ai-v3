# 06/10 — News Analysis

> **Owner agent:** News  ·  **Phase:** P2  ·  **SLA:** p50 < 10s · p95 < 30s

---

## 1. Purpose

On every new news article, classify ticker relevance, assess materiality, extract entities, and dispatch to sentiment_analysis.

## 2. Trigger

Event (`raw.news.new`)

## 3. Input Schema

Reference: `09-json-schemas/02-news-article.md`

## 4. Output Schema

Reference: `09-json-schemas/05-analysis-result.md (NewsAnalysis subtype)`

## 5. Steps

1. Receive new article event.
2. Fetch article body from PostgreSQL.
3. Call news_agent (LLM):
   - Extract tickers mentioned (regex + LLM verify).
   - Classify topics (earnings, M&A, regulatory, macro, sector, analyst rating).
   - Assess materiality (LOW/MEDIUM/HIGH/CRITICAL).
   - Summarize in 50 words (Turkish).
4. Insert analysis into PostgreSQL `news_analyses`.
5. Emit Redis event `analysis.news.complete` for sentiment_analysis + supervisor.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| LLM failure                      | Retry; fallback: rule-based ticker extraction       |
| Body too long (> 8K tokens)      | Truncate to first 6K tokens; flag `truncated: true` |

## 7. n8n Nodes

- `Webhook` (trigger from news_collector)
- `LLM` (LiteLLM: news agent)
- `Postgres` (insert)
- `Redis` (publish event)

## 8. Test Cases

1. **Happy path:** THYAO earnings article → ticker=THYAO, topic=earnings, materiality=HIGH.
2. **Edge:** Article mentions multiple tickers → `tickers: [THYAO, PGSUS]`.
3. **Failure:** LLM timeout → fallback to regex-only extraction; flag `method: regex_only`.

## 9. Idempotency

Key format: `news:{article_id}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 10s**
- p95 latency: **< 30s**
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
