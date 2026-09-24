# 07/11 — Compliance Agent

> **Phase:** P3  ·  **LLM model:** MiniMax M3  ·  **Cost budget:** ~$0.01 per call

---

## 1. Role

Pre-delivery compliance review: forbidden language, disclaimer presence, evidence citation, RBAC enforcement.

## 2. Responsibilities

- Receive decision record (post-portfolio, pre-notification).
- Check for forbidden language: "guaranteed return", "sure thing", "100% certain", "risk-free".
- Verify disclaimer block present.
- Verify every evidence item has non-null source_url.
- Verify confidence in [0, 1].
- Verify position size within constraints.
- If any check fails → BLOCK with reason.
- If all pass → APPROVE for notification.

## 3. Inputs

Reference: ``08-decision-record.md``

## 4. Outputs

Reference: ``08-decision-record.md` (with compliance_status field)`

## 5. Tools

- `regex_scan(text, forbidden_patterns)`
- `validate_disclaimer(payload)`
- `validate_evidence_citations(evidence[])`
- `check_position_constraints(decision, portfolio_constraints)`

## 6. Prompt Strategy

See `08-prompts/11-compliance-prompt.md`. Key elements:
- Conservative by default (when in doubt, BLOCK)
- Cite the specific rule that was violated
- Never approve without all checks passing

## 7. Hallucination Guards

- Compliance agent NEVER fabricates violations — only flags what is in the input.
- If input is unclear, BLOCK with reason "unclear_payload" (do not approve based on assumption).
- Forbidden-language list is hard-coded + LLM-verified (defense in depth).

## 8. Quality Checks

- `compliance_status` must be APPROVED or BLOCKED.
- If BLOCKED, `reason` must be one of enumerated values.
- Audit record must be inserted into `compliance_audits` table.

## 9. Escalation Rules

- BLOCKED decision → alert compliance team (Slack).
- 3 BLOCKED decisions from same agent in 1 hour → flag agent for review.

## 10. Cost Budget

~$0.01 per call
- Max input tokens per call: see prompt file
- Max output tokens per call: see prompt file
- Cost alert threshold: 150% of budget per call

## 11. Observability

- OTel span: `agent.compliance.invoke` with attributes `{agent_id, workflow_id, ticker, decision_id}`
- Metrics: `agent_duration_seconds`, `agent_llm_tokens_total`, `agent_failures_total{reason}`
- Logs: every LLM call logged with `{prompt_hash, model, tokens_in, tokens_out, cost_usd}`

## 12. Dependencies

- Upstream: see Inputs
- Downstream: see Outputs
- LLM: via LiteLLM only
