# 11/04 — Retrieval Examples (Concrete)

## Example 1: Technical signal "RSI=70 on THYAO"

Query Qdrant for past RSI=70 events on THYAO and their outcomes:

```python
# Build query
query_text = "RSI 70 overbought THYAO"
query_vec = await litellm.embed(query_text)

# Search news_embeddings for context
news_results = qdrant.search(
    "news_embeddings",
    query_vec,
    filter=Filter(must=[FieldCondition(key="tickers", match=MatchValue(value="THYAO"))]),
    limit=5
)

# Search decision_memory for past decisions at similar signals
decision_results = qdrant.search(
    "decision_memory",
    query_vec,
    filter=Filter(must=[FieldCondition(key="ticker", match=MatchValue(value="THYAO"))]),
    limit=5
)

# Compute hit rate
hit_rate = sum(1 for r in decision_results if r.payload.get("outcome_hit")) / len(decision_results)
# → feed into confidence calibration: if hit_rate < 0.5, cap confidence at 0.5
```

## Example 2: KAP "Q3 earnings beat" recall

```python
query_text = f"{kap.title}\n\n{kap.body[:2000]}"
query_vec = await litellm.embed(query_text)

similar_kaps = qdrant.search(
    "kap_embeddings",
    query_vec,
    filter=Filter(must=[
        FieldCondition(key="category", match=MatchValue(value="FINANCIAL_REPORT")),
        FieldCondition(key="tickers", match=MatchValue(value=kap.related_tickers[0]))
    ]),
    limit=5
)

# For each similar KAP, fetch the subsequent price move
for sk in similar_kaps:
    price_move = await fetch_price_move_after(sk.payload["published_at"], ticker, days=5)
    # Aggregate: "5 similar past earnings beats led to avg +2.3% in 5 days"
```

## Example 3: Cross-asset memory

For sector rotation decisions:
```python
query = f"Sector rotation: banks to industrials, BIST-FIN up 3% in 5d"
query_vec = await litellm.embed(query)

# Recall similar rotation patterns
similar_rotations = qdrant.search("analysis_memory", query_vec, limit=5)
# Compute: "3 similar past rotations sustained for 2+ weeks, 2 reversed in 1 week"
```
