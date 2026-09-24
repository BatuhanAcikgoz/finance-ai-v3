# 07/03 — Fundamental Agent

> **Phase:** P2  ·  **LLM model:** MiniMax M3  ·  **Cost budget:** ~$0.03 per call (longer prompt, ~3K input tokens)

---

## 1. Role

Extract financials from KAP disclosures, compute 20+ ratios, run peer comparison, output fundamental signal.

## 2. Responsibilities

- Parse KAP disclosure body (Turkish financial statements).
- Extract: revenue, EBITDA, net income, total debt, cash, equity, EPS.
- Compute ratios: P/E, P/B, EV/EBITDA, ROE, ROA, ROIC, debt/equity, current ratio, etc.
- Fetch peer set (5-10 sector peers).
- Compute percentile rank for each ratio.
- Output fundamental signal with confidence based on data freshness + peer coverage.

## 3. Inputs

Reference: ``03-kap-announcement.md` + historical financials from PostgreSQL`

## 4. Outputs

Reference: ``05-analysis-result.md` (FundamentalSignal subtype)`

## 5. Tools

- `fetch_kap_disclosure(publishing_id)`
- `fetch_ticker_fundamentals(ticker)` — historical
- `fetch_peer_set(ticker)` — from `tickers` table
- `fetch_price(ticker)` — for P/E etc.

## 6. Prompt Strategy

See `08-prompts/03-fundamental-prompt.md`. Key elements:
- Force extraction table format (so numbers are explicit, not paraphrased)
- Cite line numbers / table cells from KAP for each number
- Compute ratios deterministically in code, NOT in LLM
- LLM only interprets (bullish/bearish) — arithmetic is in Python

## 7. Hallucination Guards

- Every extracted number must cite KAP line/table.
- LLM-proposed ratios are RECOMPUTED in Python; if mismatch > 1%, alert.
- If KAP does not contain a field, output `null` — never guess.
- Peer comparison requires >= 5 peers; else confidence capped 0.4.

## 8. Quality Checks

- All non-null financials must have `source: {kap_id, line_no}`.
- Ratios computed in Python, not LLM.
- P/E > 100 or < 0 → flag for review (data quality issue).

## 9. Escalation Rules

- If quarterly earnings missing for > 2 quarters → confidence 0.2.
- If peer set < 5 → flag `peer_coverage: low`.

## 10. Cost Budget

~$0.03 per call (longer prompt, ~3K input tokens)
- Max input tokens per call: see prompt file
- Max output tokens per call: see prompt file
- Cost alert threshold: 150% of budget per call

## 11. Observability

- OTel span: `agent.fundamental.invoke` with attributes `{agent_id, workflow_id, ticker, decision_id}`
- Metrics: `agent_duration_seconds`, `agent_llm_tokens_total`, `agent_failures_total{reason}`
- Logs: every LLM call logged with `{prompt_hash, model, tokens_in, tokens_out, cost_usd}`

## 12. Dependencies

- Upstream: see Inputs
- Downstream: see Outputs
- LLM: via LiteLLM only
