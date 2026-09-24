# 07/04 — Macro Agent

> **Phase:** P2  ·  **LLM model:** MiniMax M3  ·  **Cost budget:** ~$0.02 per call

---

## 1. Role

Interpret macroeconomic releases (TCMB, TÜİK, BDDK). Assess surprise vs. consensus, estimate market impact, detect regime change.

## 2. Responsibilities

- Fetch latest macro indicator + 12-month history.
- Compare actual vs. consensus (EVDS expectations).
- Estimate impact on: BIST-100, USD/TRY, yield curve, banking sector.
- Detect regime: BULL / BEAR / RANGE / CRISIS.
- Output macro signal with confidence.

## 3. Inputs

Reference: ``01-market-data.md` (macro_indicators subtype)`

## 4. Outputs

Reference: ``05-analysis-result.md` (MacroSignal subtype)`

## 5. Tools

- `fetch_macro_history(indicator_code, months=12)`
- `fetch_consensus(indicator_code, date)`
- `fetch_bist100_history(days=30)` — for impact estimation

## 6. Prompt Strategy

See `08-prompts/04-macro-prompt.md`. Key elements:
- Quantify surprise (actual - consensus) before interpreting
- Cite historical analogs ("similar surprise in 2024-Q2 led to ...")
- Distinguish first-derivative (change) from second-derivative (acceleration)
- Regime detection is conservative: only change regime on 3rd confirming signal

## 7. Hallucination Guards

- NEVER cite a historical analog that was not returned by Qdrant.
- If consensus unavailable, output `surprise: null`, confidence capped 0.4.
- Regime change requires citing 3 confirming indicators.

## 8. Quality Checks

- `surprise` (if non-null) must equal (actual - consensus).
- `regime` must be one of {BULL, BEAR, RANGE, CRISIS}.
- `impact_estimate` for each asset class in [-5%, +5%]; outside → flag.

## 9. Escalation Rules

- Regime change → always flag for human review (macro strategist).
- CRISIS regime → alert on-call immediately.

## 10. Cost Budget

~$0.02 per call
- Max input tokens per call: see prompt file
- Max output tokens per call: see prompt file
- Cost alert threshold: 150% of budget per call

## 11. Observability

- OTel span: `agent.macro.invoke` with attributes `{agent_id, workflow_id, ticker, decision_id}`
- Metrics: `agent_duration_seconds`, `agent_llm_tokens_total`, `agent_failures_total{reason}`
- Logs: every LLM call logged with `{prompt_hash, model, tokens_in, tokens_out, cost_usd}`

## 12. Dependencies

- Upstream: see Inputs
- Downstream: see Outputs
- LLM: via LiteLLM only
