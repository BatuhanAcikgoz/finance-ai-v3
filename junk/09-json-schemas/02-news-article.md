# 09/02 — News Article Schema

> **Description:** News article from RSS or scrape

## Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://finance-ai-v3/schemas/news_article.json",
  "title": "NewsArticle",
  "type": "object",
  "properties": {
    "article_id": {"type": "string", "format": "uuid"},
    "source": {"type": "string", "enum": ["BLOOMBERG_HT", "AA", "FOREKS", "REUTERS", "BLOOMBERG", "CNBC_E", "DUNYA", "CAPITAL", "PARA", "EKONOMIM", "BIGPARA", "ANADOLU"]},
    "url": {"type": "string", "format": "uri"},
    "title": {"type": "string", "maxLength": 500},
    "summary": {"type": "string", "maxLength": 2000},
    "body": {"type": "string"},
    "author": {"type": ["string", "null"]},
    "published_at": {"$ref": "timestamp.json"},
    "ingested_at": {"$ref": "timestamp.json"},
    "language": {"type": "string", "enum": ["tr", "en"]},
    "content_hash": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    "tickers_detected": {"type": "array", "items": {"$ref": "ticker.json"}}
  },
  "required": ["article_id", "source", "url", "title", "body", "published_at", "ingested_at", "language", "content_hash"],
  "additionalProperties": false
}
```

## Usage

- **Source of truth:** `schemas/news_article.json`
- **Pydantic model:** generated via `make generate-models` to `services/*/src/*/models.py`
- **Validation:** every Kafka/Redis message validated before consumption
- **LLM output:** every LLM JSON output validated before write to DB

## Validation Rules

1. `additionalProperties: false` — extra fields rejected
2. All `required` fields must be present
3. All enums case-sensitive (UPPER_SNAKE_CASE)
4. All timestamps must include timezone
5. All percentages in [0, 1] (not 0-100)
6. All monetary values in TRY (float) unless explicitly suffixed

## Migration Path

If this schema needs to change:
1. Open PR with new version (e.g. `decision_record_v2.json`)
2. Update consumers to handle both versions during migration window
3. After all consumers updated, deprecate v1
4. Update `10-database/05-migrations.md` with migration entry
