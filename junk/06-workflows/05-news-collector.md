# 06/05 — News Collector

> **Owner agent:** News  ·  **Phase:** P1  ·  **SLA:** p50 < 30s per batch · p95 < 2 min

---

## 1. Purpose

Poll 12+ RSS feeds every 2 minutes, scrape full article text, deduplicate against last 30 days, and dispatch to news_analysis workflow.

## 2. Trigger

Schedule (every 2 min, 24/7)

## 3. Input Schema

Reference: `09-json-schemas/02-news-article.md (input: `{source, since}`)`

## 4. Output Schema

Reference: `09-json-schemas/02-news-article.md (output: article record with body)`

## 5. Steps

1. Load source registry from `news_sources` table (12 sources, each with RSS URL, parser config).
2. For each source (parallel):
   a. Fetch RSS feed.
   b. For each new item:
      - Scrape full article body from `link` (with source-specific selector).
      - Extract publish_time, title, summary, body, author.
      - Compute content hash (SHA-256 of normalized text).
      - Check Redis `news:hash:{hash}` — if exists, skip (duplicate).
      - Insert into PostgreSQL `news_articles`.
      - Set Redis `news:hash:{hash}` with 30-day TTL.
      - Emit Redis event `raw.news.new` for news_analysis workflow.
3. Log source-level stats (articles fetched, deduplicated, errors).

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| RSS feed 404                     | Mark source `active: false`; alert                  |
| Article scrape fails             | Insert with `body: null`; flag `needs_rescrape`     |
| Source blocks scraper            | Retry with rotating User-Agent; alert after 3 fails |
| Dedup hash collision             | Very rare (SHA-256); if happens, manual review      |

## 7. n8n Nodes

- `Schedule Trigger` (every 2 min)
- `RSS Feed Read`
- `HTTP Request` (article body scrape)
- `HTML Extract` (BeautifulSoup)
- `Code` (hash + dedup check)
- `Postgres` (insert)
- `Redis` (dedup key + publish event)

## 8. Test Cases

1. **Happy path:** 5 new articles from 3 sources → 5 inserted, 5 events emitted, 2 duplicates skipped.
2. **Edge:** Source temporarily down → that source skipped; others continue; alert after 3 consecutive failures.
3. **Failure:** Article body scrape 403 → body set to null; `needs_rescrape: true`; alert.

## 9. Idempotency

Key format: `news:{source}:{article_guid}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 30s per batch**
- p95 latency: **< 2 min**
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
