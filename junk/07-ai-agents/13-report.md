# 07/13 — Report Agent

> **Phase:** P2  ·  **LLM model:** MiniMax M3  ·  **Cost budget:** ~$0.04 per report (longer output, ~1500 words)

---

## 1. Role

Generate narrative reports: morning briefing, evening summary, weekly, monthly. Group decisions, summarize, propose action items.

## 2. Responsibilities

- Fetch decisions since last report.
- Group by ticker, sector, theme.
- Generate Turkish narrative for each group.
- Compose executive summary (50 words).
- Generate top-3 action items.
- Include disclaimer block.
- Respect word count limits (1500 daily, 4000 weekly, 10000 monthly).

## 3. Inputs

Reference: ``08-decision-record.md` + `06-risk-assessment.md` + `07-portfolio-state.md``

## 4. Outputs

Reference: ``10-report-payload.md``

## 5. Tools

- `fetch_decisions(since, until)`
- `fetch_risk_assessment(portfolio_id)`
- `fetch_portfolio_state(portfolio_id)`
- `render_template(template_name, context)` — Jinja2

## 6. Prompt Strategy

See `08-prompts/13-report-prompt.md`. Key elements:
- Strict word count enforcement
- Turkish narrative, professional tone (not casual)
- Every recommendation must cite decision_id (for audit trail)
- Disclaimer at top and bottom of report

## 7. Hallucination Guards

- NEVER mention a decision that is not in the input.
- NEVER cite a price that is not from `market_data` table.
- If no decisions in period, output "No actionable items today" (do not invent).
- Word count MUST be enforced (hard limit, not guideline).

## 8. Quality Checks

- Word count <= limit + 10% tolerance.
- All cited decision_ids exist in PostgreSQL.
- Disclaimer block present.
- All prices match `market_data` table.

## 9. Escalation Rules

- LLM fails → fallback to template-only report (no narrative).

## 10. Cost Budget

~$0.04 per report (longer output, ~1500 words)
- Max input tokens per call: see prompt file
- Max output tokens per call: see prompt file
- Cost alert threshold: 150% of budget per call

## 11. Observability

- OTel span: `agent.report.invoke` with attributes `{agent_id, workflow_id, ticker, decision_id}`
- Metrics: `agent_duration_seconds`, `agent_llm_tokens_total`, `agent_failures_total{reason}`
- Logs: every LLM call logged with `{prompt_hash, model, tokens_in, tokens_out, cost_usd}`

## 12. Dependencies

- Upstream: see Inputs
- Downstream: see Outputs
- LLM: via LiteLLM only
