# 07/06 — Sentiment Agent

> **Phase:** P2  ·  **LLM model:** MiniMax M3  ·  **Cost budget:** ~$0.01 per call

---

## 1. Role

Turkish NLP sentiment analysis: score sentiment on [-1, +1] scale with conviction [0,1] and key phrases.

## 2. Responsibilities

- Receive article body + news analysis.
- Score sentiment: BEARISH (-1) to BULLISH (+1), continuous.
- Score conviction: 0 to 1 (how clearly the sentiment is expressed).
- Identify 1-3 key phrases driving the sentiment.
- Aggregate per-ticker daily sentiment (conviction-weighted).

## 3. Inputs

Reference: ``05-analysis-result.md` (NewsAnalysis subtype) + `02-news-article.md``

## 4. Outputs

Reference: ``05-analysis-result.md` (SentimentAnalysis subtype)`

## 5. Tools

- `fetch_article_sentiment_history(ticker, days=30)`
- `query_similar_articles(article_hash, top_k=5)` — for context

## 6. Prompt Strategy

See `08-prompts/06-sentiment-prompt.md`. Key elements:
- Turkish financial vocabulary (kâr, zarar, beklenti, rekor, düşüş, yükseliş...)
- Distinguish factual reporting from opinion (factual → lower conviction)
- Sarcasm handling: if conflict between title and body, downgrade conviction
- Always cite key phrases (verbatim from article)

## 7. Hallucination Guards

- Key phrases MUST be verbatim from article (not paraphrased).
- If article is purely factual (no opinion), conviction <= 0.4.
- If model is uncertain, output sentiment = 0 (neutral), conviction low.
- Never output sentiment > 0.9 or < -0.9 (extreme values need 3+ confirming phrases).

## 8. Quality Checks

- `sentiment` in [-1, +1].
- `conviction` in [0, 1].
- `key_phrases[]` length 1-3, each phrase must appear in article body (substring check).

## 9. Escalation Rules

- Sarcasm detected (title/body conflict) → flag `complexity: high`.
- Sentiment > 0.8 or < -0.8 → flag for spot-check.

## 10. Cost Budget

~$0.01 per call
- Max input tokens per call: see prompt file
- Max output tokens per call: see prompt file
- Cost alert threshold: 150% of budget per call

## 11. Observability

- OTel span: `agent.sentiment.invoke` with attributes `{agent_id, workflow_id, ticker, decision_id}`
- Metrics: `agent_duration_seconds`, `agent_llm_tokens_total`, `agent_failures_total{reason}`
- Logs: every LLM call logged with `{prompt_hash, model, tokens_in, tokens_out, cost_usd}`

## 12. Dependencies

- Upstream: see Inputs
- Downstream: see Outputs
- LLM: via LiteLLM only
