# 07/10 — Backtest Agent

> **Phase:** P3  ·  **LLM model:** MiniMax M3  ·  **Cost budget:** ~$0.05 per weekly call (long analysis)

---

## 1. Role

Weekly backtest: compute hit-rate, calibration, attribution; propose weight recalibration for decision engine.

## 2. Responsibilities

- Fetch decisions from last 4 weeks.
- Fetch realized outcomes (price change over horizon).
- Compute hit-rate per stream, per confidence bucket.
- Compute calibration (Brier score).
- Call LLM to identify patterns in wrong decisions.
- Propose weight adjustments for each evidence stream.

## 3. Inputs

Reference: ``08-decision-record.md` + `01-market-data.md``

## 4. Outputs

Reference: ``10-report-payload.md` (BacktestReport subtype)`

## 5. Tools

- `fetch_decisions(start_date, end_date)`
- `fetch_realized_prices(decision_date, horizon_days=5)`
- `compute_hit_rate(decisions, outcomes)`
- `compute_brier_score(confidences, outcomes)`

## 6. Prompt Strategy

See `08-prompts/10-backtest-prompt.md`. Key elements:
- Statistical report first, narrative second
- Pattern identification (e.g. "fundamental agent underperforms in Q1 earnings season")
- Weight adjustment proposal (delta per stream, max ±20%)
- Cite specific decision_ids when giving examples

## 7. Hallucination Guards

- Hit-rate numbers must match Python computation.
- Cited decision_ids must exist in PostgreSQL.
- Weight adjustments must be in [-20%, +20%] per stream (no extreme changes).

## 8. Quality Checks

- Hit-rate in [0, 1].
- Brier score in [0, 1].
- Weight adjustments sum to 1.0 (renormalized).
- Sample size >= 30 decisions for meaningful stats; else flag `low_sample`.

## 9. Escalation Rules

- Hit-rate < 50% on >= 0.8-confidence decisions → CRITICAL alert.
- Calibration error > 0.15 → flag for prompt review.

## 10. Cost Budget

~$0.05 per weekly call (long analysis)
- Max input tokens per call: see prompt file
- Max output tokens per call: see prompt file
- Cost alert threshold: 150% of budget per call

## 11. Observability

- OTel span: `agent.backtest.invoke` with attributes `{agent_id, workflow_id, ticker, decision_id}`
- Metrics: `agent_duration_seconds`, `agent_llm_tokens_total`, `agent_failures_total{reason}`
- Logs: every LLM call logged with `{prompt_hash, model, tokens_in, tokens_out, cost_usd}`

## 12. Dependencies

- Upstream: see Inputs
- Downstream: see Outputs
- LLM: via LiteLLM only
