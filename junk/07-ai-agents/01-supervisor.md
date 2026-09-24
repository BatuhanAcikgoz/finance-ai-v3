# 07/01 — Supervisor Agent

> **Phase:** P2  ·  **LLM model:** MiniMax M3  ·  **Cost budget:** ~$0.05 per decision (1 supervisor call + 6-8 specialist calls)

---

## 1. Role

Top-level orchestrator. Receives events, decomposes into sub-tasks, dispatches to specialist agents, aggregates evidence, calls decision engine.

## 2. Responsibilities

- Receive trigger event (signal from any stream).
- Identify which specialist agents to invoke.
- Dispatch sub-tasks in parallel via Redis.
- Wait for all responses (with timeout).
- Aggregate evidence into a single pack.
- Call decision_engine workflow.
- Route final decision to compliance_check.
- Log full trace to OTel.

## 3. Inputs

Reference: `All `05-analysis-result.md` subtypes + `07-portfolio-state.md``

## 4. Outputs

Reference: ``08-decision-record.md` (draft, pre-compliance)`

## 5. Tools

- `dispatch_agent(agent_name, task_payload)` — async, returns task_id
- `await_agent(task_id, timeout)` — async
- `aggregate_evidence(results[])` — combines into evidence pack
- `query_memory(similar_to, top_k)` — Qdrant similarity search
- `read_portfolio(portfolio_id)` — fetch portfolio state

## 6. Prompt Strategy

See `08-prompts/01-supervisor-prompt.md`. Supervisor prompt emphasizes:
- Decomposition discipline (which agents to call, in what order)
- Timeout handling (do not wait forever for slow agent)
- Evidence pack assembly (consistent schema)
- Confidence propagation (each evidence item carries confidence)

## 7. Hallucination Guards

- Supervisor NEVER fabricates evidence — it only relays what specialist agents returned.
- If a specialist agent returns no signal, supervisor marks `evidence_missing: true` for that stream.
- If < 3 streams have evidence, supervisor emits INSUFFICIENT_EVIDENCE decision (per master prompt §2.4).

## 8. Quality Checks

- All dispatched tasks must complete within 60s, else timeout.
- Evidence pack must contain >= 3 items, else INSUFFICIENT_EVIDENCE.
- All evidence items must have non-null `source_id` and `retrieved_at`.

## 9. Escalation Rules

- If specialist agent fails 3x in a row → escalate to on-call (Slack).
- If evidence is heavily contradictory (score > 0.6) → flag for human review.

## 10. Cost Budget

~$0.05 per decision (1 supervisor call + 6-8 specialist calls)
- Max input tokens per call: see prompt file
- Max output tokens per call: see prompt file
- Cost alert threshold: 150% of budget per call

## 11. Observability

- OTel span: `agent.supervisor.invoke` with attributes `{agent_id, workflow_id, ticker, decision_id}`
- Metrics: `agent_duration_seconds`, `agent_llm_tokens_total`, `agent_failures_total{reason}`
- Logs: every LLM call logged with `{prompt_hash, model, tokens_in, tokens_out, cost_usd}`

## 12. Dependencies

- Upstream: see Inputs
- Downstream: see Outputs
- LLM: via LiteLLM only
