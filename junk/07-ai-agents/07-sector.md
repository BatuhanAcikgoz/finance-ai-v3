# 07/07 — Sector Agent

> **Phase:** P2  ·  **LLM model:** MiniMax M3  ·  **Cost budget:** ~$0.02 per call

---

## 1. Role

Sector rotation analysis: identify leading/lagging sectors, relative strength shifts, rotation signals.

## 2. Responsibilities

- Fetch 14 sector indices for 250 days.
- Compute returns (1d/1w/1m/3m/YTD), breadth, relative strength.
- Identify rotation patterns (e.g. bank → industrial).
- Output per-sector signal + rotation narrative.

## 3. Inputs

Reference: ``01-market-data.md` (sector indices)`

## 4. Outputs

Reference: ``05-analysis-result.md` (SectorAnalysis subtype)`

## 5. Tools

- `fetch_sector_indices(days=250)`
- `fetch_sector_constituents(sector_code)`
- `compute_correlation_matrix(returns, window=90)`

## 6. Prompt Strategy

See `08-prompts/07-sector-prompt.md`. Key elements:
- Quantitative first (returns table), narrative second
- Rotation detected only on 5+ day trend (not 1-day noise)
- Cite specific sectors by BIST code (BIST-FIN, BIST-IND, etc.)

## 7. Hallucination Guards

- Sector returns in output must match computed values (Python cross-check).
- NEVER cite a sector that is not in BIST official list.
- Rotation signal requires >= 5 days of confirming trend.

## 8. Quality Checks

- All sector codes valid.
- Returns match Python computation (cross-validation).
- Rotation narrative mentions specific sectors + direction.

## 9. Escalation Rules

- If 3+ sectors show > 5% move in single day → flag `high_volatility`.

## 10. Cost Budget

~$0.02 per call
- Max input tokens per call: see prompt file
- Max output tokens per call: see prompt file
- Cost alert threshold: 150% of budget per call

## 11. Observability

- OTel span: `agent.sector.invoke` with attributes `{agent_id, workflow_id, ticker, decision_id}`
- Metrics: `agent_duration_seconds`, `agent_llm_tokens_total`, `agent_failures_total{reason}`
- Logs: every LLM call logged with `{prompt_hash, model, tokens_in, tokens_out, cost_usd}`

## 12. Dependencies

- Upstream: see Inputs
- Downstream: see Outputs
- LLM: via LiteLLM only
