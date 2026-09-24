# 07/05 — News Agent

> **Phase:** P2  ·  **LLM model:** MiniMax M3  ·  **Cost budget:** ~$0.01 per call

---

## 1. Role

Classify news articles: extract tickers, identify topic, assess materiality, summarize in 50 words (Turkish).

## 2. Responsibilities

- Receive article body.
- Extract BIST tickers mentioned (regex + LLM verify).
- Classify topic: earnings, M&A, regulatory, macro, sector, analyst rating, IPO, capital action.
- Assess materiality: LOW/MEDIUM/HIGH/CRITICAL.
- Summarize in Turkish, 50 words.
- Output structured news analysis.

## 3. Inputs

Reference: ``02-news-article.md` (body + metadata)`

## 4. Outputs

Reference: ``05-analysis-result.md` (NewsAnalysis subtype)`

## 5. Tools

- `fetch_ticker_list()` — for regex matching
- `fetch_article_history(ticker, days=7)` — for context
- `query_similar_news(article_hash, top_k=3)` — Qdrant

## 6. Prompt Strategy

See `08-prompts/05-news-prompt.md`. Key elements:
- Strict JSON output
- Force tickers as array (even if single)
- Materiality rubric explicit (HIGH = moves price > 2%)
- Summary in Turkish, max 50 words

## 7. Hallucination Guards

- NEVER output a ticker that does not exist in BIST.
- If article is generic macro (no specific ticker), `tickers: []`.
- If unsure about materiality, default MEDIUM (not HIGH).
- If article body < 100 chars, flag `low_quality_source`.

## 8. Quality Checks

- All `tickers[]` must exist in `tickers` table.
- `topic` must be one of 8 enumerated values.
- `materiality` must be one of {LOW, MEDIUM, HIGH, CRITICAL}.
- Summary word count <= 60.

## 9. Escalation Rules

- CRITICAL materiality → alert supervisor immediately.
- Article mentions portfolio holding → flag for portfolio agent.

## 10. Cost Budget

~$0.01 per call
- Max input tokens per call: see prompt file
- Max output tokens per call: see prompt file
- Cost alert threshold: 150% of budget per call

## 11. Observability

- OTel span: `agent.news.invoke` with attributes `{agent_id, workflow_id, ticker, decision_id}`
- Metrics: `agent_duration_seconds`, `agent_llm_tokens_total`, `agent_failures_total{reason}`
- Logs: every LLM call logged with `{prompt_hash, model, tokens_in, tokens_out, cost_usd}`

## 12. Dependencies

- Upstream: see Inputs
- Downstream: see Outputs
- LLM: via LiteLLM only
