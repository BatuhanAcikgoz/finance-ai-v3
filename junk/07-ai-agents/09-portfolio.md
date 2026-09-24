# 07/09 — Portfolio Agent

> **Phase:** P2  ·  **LLM model:** None (deterministic, numpy/pandas)  ·  **Cost budget:** $0 per call (no LLM)

---

## 1. Role

Compute portfolio context for decisions: current exposure, post-trade exposure, position sizing, drift from target.

## 2. Responsibilities

- Fetch portfolio holdings + target weights.
- Compute current exposure to ticker.
- Compute post-trade exposure (if decision executed).
- Compute position size suggestion (Kelly fraction × confidence × risk budget).
- Compute drift from target weights.
- Enforce portfolio constraints (max position, max sector, etc.).

## 3. Inputs

Reference: ``07-portfolio-state.md` + `08-decision-record.md` (draft)`

## 4. Outputs

Reference: ``08-decision-record.md` (enriched with portfolio_context)`

## 5. Tools

- `fetch_portfolio(portfolio_id)`
- `compute_kelly_fraction(confidence, win_rate, win_loss_ratio)`
- `compute_drift(current_weights, target_weights)`
- `apply_constraints(suggested_size, portfolio_constraints)`

## 6. Prompt Strategy

N/A — deterministic. Kelly formula + drift + constraint enforcement in Python.

## 7. Hallucination Guards

N/A — deterministic.

## 8. Quality Checks

- Suggested size in [0, max_position_size].
- Post-trade exposure <= max_sector_exposure.
- Kelly fraction in [0, 0.25] (quarter-Kelly cap).
- Drift > 5% → flag for rebalance.

## 9. Escalation Rules

- Kelly fraction negative → skip recommendation (no edge).
- Drift > 10% → emit rebalance alert.

## 10. Cost Budget

$0 per call (no LLM)
- Max input tokens per call: see prompt file
- Max output tokens per call: see prompt file
- Cost alert threshold: 150% of budget per call

## 11. Observability

- OTel span: `agent.portfolio.invoke` with attributes `{agent_id, workflow_id, ticker, decision_id}`
- Metrics: `agent_duration_seconds`, `agent_llm_tokens_total`, `agent_failures_total{reason}`
- Logs: every LLM call logged with `{prompt_hash, model, tokens_in, tokens_out, cost_usd}`

## 12. Dependencies

- Upstream: see Inputs
- Downstream: see Outputs
- LLM: via LiteLLM only
