# 10/03 — Qdrant Collections

> Qdrant 1.10. Vector store for semantic search across news, KAP, decisions, and analysis results.

## Collections

| Collection          | Vector size | Distance   | Retention | Purpose                                  |
|---------------------|-------------|------------|-----------|------------------------------------------|
| `news_embeddings`   | 3072        | Cosine     | 2 years   | News article semantic search             |
| `kap_embeddings`    | 3072        | Cosine     | 5 years   | KAP disclosure semantic search           |
| `analysis_memory`   | 3072        | Cosine     | 2 years   | Analysis result memory                   |
| `decision_memory`   | 3072        | Cosine     | 2 years   | Decision record memory (for backtest)    |
| `similar_events`    | 3072        | Cosine     | 2 years   | Aggregated "similar to" index            |

## Collection Creation

```python
from qdrant_client import QdrantClient
from qdrant_client.http import models

client = QdrantClient(url="http://qdrant:6333")

client.create_collection(
    collection_name="news_embeddings",
    vectors_config=models.VectorParams(size=3072, distance=models.Distance.COSINE),
    on_disk_payload=True,
    optimizers_config=models.OptimizersConfigDiff(
        indexing_threshold=20000,
        default_segment_number=4
    )
)
```

## Payload Schema (per collection)

### `news_embeddings` payload
```json
{
  "article_id": "uuid",
  "source": "BLOOMBERG_HT",
  "published_at": "2026-07-28T10:30:00+03:00",
  "tickers": ["THYAO"],
  "topic": "EARNINGS",
  "materiality": "HIGH"
}
```

### `kap_embeddings` payload
```json
{
  "publishing_id": "string",
  "published_at": "ISO 8601",
  "category": "FINANCIAL_REPORT",
  "tickers": ["THYAO"],
  "is_material": true
}
```

### `decision_memory` payload
```json
{
  "decision_id": "uuid",
  "ticker": "THYAO",
  "action": "BUY",
  "confidence": 0.78,
  "effective_at": "ISO 8601",
  "outcome_hit": true,
  "realized_return_5d_pct": 0.032
}
```

## Indexes (payload filters)

```python
client.create_payload_index("news_embeddings", "tickers", models.PayloadSchemaType.KEYWORD)
client.create_payload_index("news_embeddings", "published_at", models.PayloadSchemaType.DATETIME)
client.create_payload_index("news_embeddings", "materiality", models.PayloadSchemaType.KEYWORD)
```
