# 09/10 — Report Payload Schema

> **Description:** Report (morning/evening/weekly/monthly)

## Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://finance-ai-v3/schemas/report_payload.json",
  "title": "ReportPayload",
  "type": "object",
  "properties": {
    "report_id": {"type": "string", "format": "uuid"},
    "report_type": {"type": "string", "enum": ["MORNING_BRIEFING", "EVENING_SUMMARY", "WEEKLY", "MONTHLY", "BACKTEST_REPORT"]},
    "period_start": {"$ref": "timestamp.json"},
    "period_end": {"$ref": "timestamp.json"},
    "portfolio_id": {"type": "string"},
    "executive_summary_tr": {"type": "string", "maxLength": 600},
    "decisions_count": {"type": "integer", "minimum": 0},
    "decision_groups": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "ticker": {"$ref": "ticker.json"},
          "decision_ids": {"type": "array", "items": {"type": "string"}},
          "narrative_tr": {"type": "string", "maxLength": 2000}
        }
      }
    },
    "action_items_tr": {"type": "array", "maxItems": 3, "items": {"type": "string", "maxLength": 300}},
    "disclaimer_tr": {"type": "string"},
    "html_body": {"type": "string"},
    "word_count": {"type": "integer"},
    "generated_at": {"$ref": "timestamp.json"},
    "data_completeness": {"type": "string", "enum": ["complete", "partial", "missing"]}
  },
  "required": ["report_id", "report_type", "period_start", "period_end", "portfolio_id", "executive_summary_tr", "decisions_count", "disclaimer_tr", "word_count", "generated_at", "data_completeness"],
  "additionalProperties": false
}
```

## Usage

- **Source of truth:** `schemas/report_payload.json`
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
