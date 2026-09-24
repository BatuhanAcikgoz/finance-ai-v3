# 07/08 — Risk Agent

> **Phase:** P2  ·  **LLM model:** None (deterministic, numpy/pandas)  ·  **Cost budget:** $0 per call (no LLM)

---

## 1. Role

Compute risk metrics: VaR, CVaR, beta, tracking error, concentration, factor exposures. No LLM — pure quantitative.

## 2. Responsibilities

- Fetch 1-year price history for portfolio holdings + BIST-100.
- Compute 1-day 95% VaR (historical simulation).
- Compute 1-day 95% CVaR.
- Compute beta to BIST-100, tracking error.
- Compute HHI concentration.
- Compute sector + style exposures.
- Compare to portfolio risk budget; alert if exceeded.

## 3. Inputs

Reference: ``07-portfolio-state.md` + price history`

## 4. Outputs

Reference: ``06-risk-assessment.md``

## 5. Tools

- `fetch_price_history(ticker, days=252)`
- `compute_var(returns, alpha=0.95)`
- `compute_cvar(returns, alpha=0.95)`
- `compute_correlation(returns_matrix)` — with Ledoit-Wolf shrinkage
- `compute_hhi(weights)`

## 6. Prompt Strategy

N/A — deterministic computation. No LLM call.

## 7. Hallucination Guards

N/A — deterministic. Inputs are validated; outputs are computed.

## 8. Quality Checks

- VaR in [-10%, 0] (sane range for 1-day 95%).
- Beta in [-2, +3] (sane range).
- HHI in [1/N, 1.0] where N = number of holdings.
- If any check fails → use shrinkage estimator; flag.

## 9. Escalation Rules

- VaR > 5% → CRITICAL risk alert.
- Single-holding weight > 25% → concentration alert.
- Beta > 1.5 → high-beta alert.

## 10. Cost Budget

$0 per call (no LLM)
- Max input tokens per call: see prompt file
- Max output tokens per call: see prompt file
- Cost alert threshold: 150% of budget per call

## 11. Observability

- OTel span: `agent.risk.invoke` with attributes `{agent_id, workflow_id, ticker, decision_id}`
- Metrics: `agent_duration_seconds`, `agent_llm_tokens_total`, `agent_failures_total{reason}`
- Logs: every LLM call logged with `{prompt_hash, model, tokens_in, tokens_out, cost_usd}`

## 12. Dependencies

- Upstream: see Inputs
- Downstream: see Outputs
- LLM: via LiteLLM only
