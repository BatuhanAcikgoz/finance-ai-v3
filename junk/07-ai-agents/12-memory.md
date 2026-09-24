# 07/12 — Memory Agent

> **Phase:** P2  ·  **LLM model:** None (deterministic, embedding API + Qdrant)  ·  **Cost budget:** ~$0.001 per embedding (much cheaper than LLM)

---

## 1. Role

Embed every analysis result, KAP, news, and decision into Qdrant for historical similarity search. Retrieve similar events on demand.

## 2. Responsibilities

- Build text representation of each record.
- Call embedding API (text-embedding-3-large via LiteLLM).
- Insert into appropriate Qdrant collection.
- On retrieval request: embed query, search top-K, return with payload + score.
- Maintain 2-year retention (TTL on collections).

## 3. Inputs

Reference: `All analysis result schemas + `08-decision-record.md``

## 4. Outputs

Reference: ``05-analysis-result.md` (SimilaritySearch subtype) — list of similar past events`

## 5. Tools

- `embed(text)` — via LiteLLM
- `qdrant.insert(collection, vector, payload)`
- `qdrant.search(collection, query_vector, top_k, filter)`
- `qdrant.set_ttl(collection, days=730)`

## 6. Prompt Strategy

N/A — deterministic. Embedding + vector search only.

## 7. Hallucination Guards

N/A — deterministic. Retrieved items come from Qdrant with scores; agent only returns them.

## 8. Quality Checks

- Embedding vector length = 3072 (text-embedding-3-large).
- Qdrant search returns <= top_k results.
- Each result has score in [0, 1].

## 9. Escalation Rules

- Qdrant unavailable → flag `memory_unavailable`; supervisor downgrades confidence.

## 10. Cost Budget

~$0.001 per embedding (much cheaper than LLM)
- Max input tokens per call: see prompt file
- Max output tokens per call: see prompt file
- Cost alert threshold: 150% of budget per call

## 11. Observability

- OTel span: `agent.memory.invoke` with attributes `{agent_id, workflow_id, ticker, decision_id}`
- Metrics: `agent_duration_seconds`, `agent_llm_tokens_total`, `agent_failures_total{reason}`
- Logs: every LLM call logged with `{prompt_hash, model, tokens_in, tokens_out, cost_usd}`

## 12. Dependencies

- Upstream: see Inputs
- Downstream: see Outputs
- LLM: via LiteLLM only
