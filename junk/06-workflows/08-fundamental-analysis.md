# 06/08 — Fundamental Analysis

> **Owner agent:** Fundamental  ·  **Phase:** P2  ·  **SLA:** p50 < 30s · p95 < 90s

---

## 1. Purpose

On material KAP disclosure (quarterly earnings, dividend, M&A), run fundamental agent: extract financials, compute 20+ ratios, run peer comparison.

## 2. Trigger

Event (`raw.kap.material`)

## 3. Input Schema

Reference: `09-json-schemas/03-kap-announcement.md + 01-market-data.md (price)`

## 4. Output Schema

Reference: `09-json-schemas/05-analysis-result.md (FundamentalAnalysis subtype)`

## 5. Steps

1. Receive material KAP event.
2. Fetch disclosure body from PostgreSQL.
3. Call fundamental_agent (LLM via LiteLLM):
   - Extract: revenue, EBITDA, net income, total debt, cash, equity, EPS, dividends.
   - Compute ratios: P/E, P/B, EV/EBITDA, ROE, ROA, ROIC, debt/equity, current ratio, etc.
   - Identify peer set (sector peers from `tickers` table).
   - Fetch peer ratios; compute percentile rank.
4. Insert analysis into PostgreSQL `fundamental_analyses` table.
5. Embed analysis into Qdrant `analysis_memory`.
6. Emit Redis event `analysis.fundamental.complete` for supervisor agent.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| LLM returns invalid JSON         | Repair attempt (1 retry); else INSUFFICIENT_EVIDENCE|
| LLM hallucinates numbers         | Cross-check vs. raw KAP text; if mismatch → reject  |
| Peer set empty                   | Skip percentile; flag `peer_data: false`            |

## 7. n8n Nodes

- `Webhook` (trigger from kap_collector)
- `LLM` (LiteLLM: fundamental agent prompt)
- `Postgres` (insert + fetch peer data)
- `Qdrant` (embed)
- `Redis` (publish complete event)

## 8. Test Cases

1. **Happy path:** Quarterly earnings KAP → 20 ratios computed → peer rank calculated → event emitted.
2. **Edge:** KAP with no financials (e.g. board change) → `data_completeness: "no_financials"`.
3. **Failure:** LLM returns text not JSON → repair prompt; if still fails → INSUFFICIENT_EVIDENCE.

## 9. Idempotency

Key format: `fundamental:{kap_publishing_id}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 30s**
- p95 latency: **< 90s**
- Failure rate target: **< 1%**

## 11. Observability

- Every step emits OpenTelemetry span with `workflow_id`, `step_id`, `idempotency_key`.
- Workflow-level metrics: `workflow_duration_seconds`, `workflow_step_failures_total`, `workflow_retries_total`.
- All logs JSON-structured, `workflow_id` as correlation field.

## 12. Dependencies

- Upstream: see trigger
- Downstream: see output schema consumers
- External APIs: see step list
- LLM calls: via LiteLLM only (never direct SDK)
