# 11/02 — Embedding Pipeline

## Pipeline

```
record (PG row)
    │
    ▼
text_builder (per-collection)
    │
    ▼
LiteLLM.embed("text-embedding-3-large")
    │
    ▼
Qdrant.upsert(collection, vector, payload)
    │
    ▼
PG row.embedded_in_qdrant = true
```

## Text Builder Per Collection

### news_embeddings
```
f"{title}\n\n{summary}\n\n{body[:2000]}"
```

### kap_embeddings
```
f"KAP/{category}\n\n{title}\n\n{summary}\n\n{body}"
```

### analysis_memory
```
f"{analysis_type} on {ticker} at {effective_at}\n\nDirection: {direction}\nConfidence: {confidence}\n\nReasoning: {reasoning}"
```

### decision_memory
```
f"Decision on {ticker} at {effective_at}\nAction: {action}\nConfidence: {confidence}\n\nEvidence:\n{evidence_summary}\n\nReasoning: {supervisor_reasoning}\n\nOutcome: {outcome_hit if evaluated else 'pending'}"
```

## Chunking Strategy

- If text > 8000 chars: chunk into 4000-char overlapping windows (overlap 500)
- Each chunk → separate vector with `chunk_index` in payload
- Retrieval aggregates top-K across chunks
