# 11 — Qdrant Vector Store Overview

> Qdrant 1.10. Embedding model: `text-embedding-3-large` (3072 dims) via LiteLLM.

## Purpose

Finance AI V3 uses Qdrant as a **memory layer**:
- Recall similar historical events when a new signal occurs
- Improve confidence calibration ("similar signals in the past had 65% hit rate")
- Provide context to LLM agents ("here are 5 similar past KAP disclosures")

## Collections (recap)

| Collection          | Count (1yr est.) | Vector size | Insert rate     |
|---------------------|------------------|-------------|-----------------|
| `news_embeddings`   | ~1.8M            | 3072        | ~5,000/day      |
| `kap_embeddings`    | ~150K            | 3072        | ~500/day        |
| `analysis_memory`   | ~365K            | 3072        | ~1,000/day      |
| `decision_memory`   | ~365K            | 3072        | ~1,000/day      |
| `similar_events`    | ~50K             | 3072        | aggregated       |

## Hybrid Search Pattern

Finance AI V3 uses **hybrid search**: combine vector similarity + payload filters.

```python
results = client.search(
    collection_name="news_embeddings",
    query_vector=embedding,
    query_filter=models.Filter(
        must=[
            models.FieldCondition(key="tickers", match=models.MatchValue(value="THYAO")),
            models.FieldCondition(key="published_at", range=models.DatetimeRange(gte="2024-01-01"))
        ]
    ),
    limit=10,
    with_payload=True
)
```

## Performance Targets

| Metric                          | Target      |
|---------------------------------|-------------|
| p50 search latency              | < 50 ms     |
| p95 search latency              | < 200 ms    |
| Recall@10 (labeled eval set)    | > 0.85      |
| Insert throughput               | > 1000/s    |
| Collection size (1yr)           | ~3M vectors |
| Disk usage (1yr)                | ~50 GB      |
