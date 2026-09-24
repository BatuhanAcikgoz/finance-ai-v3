# 09/09 — Alert Event Schema

> **Description:** Alert dispatched to user

## Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://finance-ai-v3/schemas/alert_event.json",
  "title": "AlertEvent",
  "type": "object",
  "properties": {
    "alert_id": {"type": "string", "format": "uuid"},
    "decision_id": {"type": "string"},
    "severity": {"type": "string", "enum": ["INFO", "WARN", "CRITICAL", "EMERGENCY"]},
    "ticker": {"$ref": "ticker.json"},
    "title_tr": {"type": "string", "maxLength": 200},
    "body_tr": {"type": "string", "maxLength": 2000},
    "action_suggested": {"type": "string", "enum": ["BUY", "SELL", "HOLD", "REDUCE", "REVIEW"]},
    "channels": {"type": "array", "items": {"type": "string", "enum": ["EMAIL", "SLACK", "DASHBOARD_WS"]}},
    "dedup_hash": {"type": "string"},
    "sent_at": {"$ref": "timestamp.json"},
    "delivered_at": {"$ref": "timestamp.json"}
  },
  "required": ["alert_id", "severity", "ticker", "title_tr", "body_tr", "channels", "sent_at"],
  "additionalProperties": false
}
```

## Usage

- **Source of truth:** `schemas/alert_event.json`
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
