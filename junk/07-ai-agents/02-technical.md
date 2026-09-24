# 07/02 — Technical Agent

> **Phase:** P1  ·  **LLM model:** MiniMax M3  ·  **Cost budget:** ~$0.01 per call (1 LLM call, ~1K input + 300 output tokens)

---

## 1. Role

Interpret technical indicators and signal events. Translate RSI=72 + MACD bearish divergence into a structured signal: {direction, strength, confidence, reasoning}.

## 2. Responsibilities

- Receive indicator snapshot for a ticker.
- Identify the 2-3 most relevant signals.
- Cross-validate signals (do not over-count cointegrated indicators).
- Output structured signal: BULLISH/BEARISH/NEUTRAL + strength 0-1 + confidence 0-1.
- Cite which indicators drove the assessment.

## 3. Inputs

Reference: ``05-analysis-result.md` (TechnicalIndicators subtype) — 40+ indicators for one ticker`

## 4. Outputs

Reference: ``05-analysis-result.md` (TechnicalSignal subtype): `{direction, strength, confidence, indicators_referenced[], reasoning}``

## 5. Tools

- `fetch_indicators(ticker, timeframe)` — from PostgreSQL `technical_indicators` table
- `query_similar_signals(signal_context, top_k=5)` — Qdrant
- `fetch_price_history(ticker, days)` — for context

## 6. Prompt Strategy

See `08-prompts/02-technical-prompt.md`. Key elements:
- Strict JSON output schema
- Force citation of indicators used (no vague "looks bullish")
- Confidence based on indicator agreement (not strength)
- Distinguish signal strength (magnitude) from confidence (reliability)

## 7. Hallucination Guards

- NEVER cite an indicator that was not in the input.
- If RSI value in input is 65, output MUST say 65 — not 70 or 75.
- If input is missing data, output `confidence: 0` and `reasoning: "insufficient data"`.
- Cross-check: if input has RSI=30 (oversold) but agent outputs BULLISH, force re-prompt.

## 8. Quality Checks

- All `indicators_referenced[]` must exist in input.
- `direction` must be one of {BULLISH, BEARISH, NEUTRAL}.
- `strength` and `confidence` in [0, 1].
- If confidence < 0.3, reasoning MUST mention data quality issue.

## 9. Escalation Rules

- If indicators conflict heavily (e.g. RSI oversold but MACD bullish crossover) → confidence capped 0.5.
- If similar historical signals (Qdrant) had < 50% hit rate → confidence capped 0.5.

## 10. Cost Budget

~$0.01 per call (1 LLM call, ~1K input + 300 output tokens)
- Max input tokens per call: see prompt file
- Max output tokens per call: see prompt file
- Cost alert threshold: 150% of budget per call

## 11. Observability

- OTel span: `agent.technical.invoke` with attributes `{agent_id, workflow_id, ticker, decision_id}`
- Metrics: `agent_duration_seconds`, `agent_llm_tokens_total`, `agent_failures_total{reason}`
- Logs: every LLM call logged with `{prompt_hash, model, tokens_in, tokens_out, cost_usd}`

## 12. Dependencies

- Upstream: see Inputs
- Downstream: see Outputs
- LLM: via LiteLLM only
