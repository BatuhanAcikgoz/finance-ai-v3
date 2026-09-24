# 11/01 — Qdrant Collections (detailed)

(see `10-database/03-qdrant-collections.md` for schema)

## Per-Collection Strategy

### news_embeddings
- Vector: title + summary + first 2000 chars of body
- Payload filters: `tickers`, `source`, `published_at`, `topic`, `materiality`
- TTL: 2 years (auto-delete via background job)
- Use case: "show me similar news for THYAO in last 6 months"

### kap_embeddings
- Vector: title + summary + body
- Payload filters: `publishing_id`, `category`, `tickers`, `is_material`, `published_at`
- TTL: 5 years (longer, regulatory)
- Use case: "show me similar past quarterly earnings disclosures"

### analysis_memory
- Vector: ticker + analysis type + reasoning
- Payload filters: `ticker`, `analysis_type`, `direction`, `confidence`
- TTL: 2 years
- Use case: "what did technical analysis say about THYAO 3 months ago"

### decision_memory
- Vector: ticker + action + reasoning + evidence summary
- Payload filters: `ticker`, `action`, `confidence_bucket`, `outcome_hit`
- TTL: 2 years
- Use case: "show me past BUY decisions on THYAO with confidence > 0.7 and their outcomes"

### similar_events
- Vector: aggregated event signature
- Payload filters: `event_type`, `tickers`, `date`
- TTL: 2 years
- Use case: "have we seen a similar pattern (technical + fundamental + news) before"
