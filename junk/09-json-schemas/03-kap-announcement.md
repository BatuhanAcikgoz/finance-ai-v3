# 09/03 — Kap Announcement Schema

> **Description:** KAP disclosure (Kamuyu Aydınlatma Platformu)

## Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://finance-ai-v3/schemas/kap_announcement.json",
  "title": "KapAnnouncement",
  "type": "object",
  "properties": {
    "publishing_id": {"type": "string"},
    "title": {"type": "string"},
    "summary": {"type": "string"},
    "body": {"type": "string"},
    "category": {"type": "string", "enum": ["FINANCIAL_REPORT", "DIVIDEND", "MA", "BOARD_CHANGE", "CAPITAL_ACTION", "DISCLOSURE", "MATERIAL_EVENT", "GENERAL_ASSEMBLY", "AUDITOR", "RATING", "LAWSUIT", "INSIDER_TRADING", "OTHER"]},
    "related_tickers": {"type": "array", "items": {"$ref": "ticker.json"}},
    "is_material": {"type": "boolean"},
    "published_at": {"$ref": "timestamp.json"},
    "ingested_at": {"$ref": "timestamp.json"},
    "source_url": {"type": "string", "format": "uri"},
    "classification_confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "needs_review": {"type": "boolean"}
  },
  "required": ["publishing_id", "title", "body", "category", "related_tickers", "is_material", "published_at", "ingested_at", "source_url"],
  "additionalProperties": false
}
```

## Usage

- **Source of truth:** `schemas/kap_announcement.json`
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
