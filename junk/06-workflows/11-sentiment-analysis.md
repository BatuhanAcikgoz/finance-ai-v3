# 06/11 — Sentiment Analysis

> **Owner agent:** Sentiment  ·  **Phase:** P2  ·  **SLA:** p50 < 10s · p95 < 30s

---

## 1. Purpose

On every news_analysis completion, run Turkish NLP sentiment analysis and aggregate per-ticker daily sentiment.

## 2. Trigger

Event (`analysis.news.complete`)

## 3. Input Schema

Reference: `09-json-schemas/05-analysis-result.md (NewsAnalysis)`

## 4. Output Schema

Reference: `09-json-schemas/05-analysis-result.md (SentimentAnalysis subtype)`

## 5. Steps

1. Receive news analysis event.
2. Fetch article body + summary.
3. Call sentiment_agent (LLM):
   - Score sentiment: BEARISH (-1) to BULLISH (+1) on [-1, +1] scale.
   - Score conviction: 0 to 1.
   - Identify key phrases driving sentiment.
4. Insert into PostgreSQL `sentiment_analyses`.
5. Aggregate: for each ticker mentioned, compute daily weighted sentiment (conviction-weighted).
6. Update Redis `sentiment:{ticker}:daily` with aggregate.
7. Emit Redis event `analysis.sentiment.complete`.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| LLM failure                      | Retry; fallback to VADER (Turkish-adapted)          |
| Sarcasm/irony                    | Confidence downgraded; flag `complexity: high`      |

## 7. n8n Nodes

- `Webhook` (trigger from news_analysis)
- `LLM` (LiteLLM: sentiment agent)
- `Postgres` (insert)
- `Redis` (publish event + update aggregate)

## 8. Test Cases

1. **Happy path:** "THYAO beat expectations" → sentiment +0.7, conviction 0.8.
2. **Edge:** Neutral article → sentiment 0.0, conviction 0.3.
3. **Failure:** LLM returns out-of-range → clamp; alert.

## 9. Idempotency

Key format: `sentiment:{article_id}`
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
