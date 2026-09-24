# 11/03 — Search Patterns

## Pattern 1: Similar News for Ticker
```python
query = f"THYAO earnings beat"
query_vec = await litellm.embed(query)
results = qdrant.search(
    collection_name="news_embeddings",
    query_vector=query_vec,
    query_filter=Filter(must=[
        FieldCondition(key="tickers", match=MatchValue(value="THYAO")),
        FieldCondition(key="published_at", range=DatetimeRange(gte="2024-01-01"))
    ]),
    limit=10
)
```

## Pattern 2: Similar Past Decisions
```python
query = f"BUY THYAO confidence 0.75"
query_vec = await litellm.embed(query)
results = qdrant.search(
    collection_name="decision_memory",
    query_vector=query_vec,
    query_filter=Filter(must=[
        FieldCondition(key="ticker", match=MatchValue(value="THYAO")),
        FieldCondition(key="action", match=MatchValue(value="BUY"))
    ]),
    limit=5
)
# Then compute hit rate: results.filter(r => r.payload.outcome_hit).count / results.count
```

## Pattern 3: Similar KAP Disclosures
```python
query = kap_disclosure.body[:2000]
query_vec = await litellm.embed(query)
results = qdrant.search(
    collection_name="kap_embeddings",
    query_vector=query_vec,
    query_filter=Filter(must=[
        FieldCondition(key="category", match=MatchValue(value="FINANCIAL_REPORT"))
    ]),
    limit=5
)
```

## Pattern 4: Cross-Collection Memory Recall
For complex decisions, query multiple collections in parallel:
```python
tasks = [
    qdrant.search("news_embeddings", vec, filter=ticker_filter, limit=5),
    qdrant.search("kap_embeddings", vec, filter=ticker_filter, limit=5),
    qdrant.search("decision_memory", vec, filter=ticker_filter, limit=5),
    qdrant.search("analysis_memory", vec, filter=ticker_filter, limit=5),
]
results = await asyncio.gather(*tasks)
```
