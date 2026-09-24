# 09/08 — Decision Record Schema

> **Description:** Final decision record (the most important schema)

## Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://finance-ai-v3/schemas/decision_record.json",
  "title": "DecisionRecord",
  "type": "object",
  "properties": {
    "decision_id": {"type": "string", "format": "uuid"},
    "portfolio_id": {"type": "string"},
    "ticker": {"$ref": "ticker.json"},
    "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD", "REDUCE", "INSUFFICIENT_EVIDENCE"]},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "position_size_pct": {"type": "number", "minimum": 0, "maximum": 0.25},
    "evidence": {"type": "array", "items": {"$ref": "evidence.json"}, "minItems": 0},
    "evidence_count": {"type": "integer", "minimum": 0},
    "contradiction_score": {"type": "number", "minimum": 0, "maximum": 1},
    "supervisor_reasoning": {"type": "string", "maxLength": 1000},
    "portfolio_context": {
      "type": "object",
      "properties": {
        "current_weight": {"type": "number"},
        "post_trade_weight": {"type": "number"},
        "kelly_fraction": {"type": "number"},
        "drift_pct": {"type": "number"}
      }
    },
    "compliance_status": {"type": "string", "enum": ["PENDING", "APPROVED", "BLOCKED"]},
    "compliance_reason": {"type": ["string", "null"]},
    "effective_at": {"$ref": "timestamp.json"},
    "created_at": {"$ref": "timestamp.json"},
    "data_completeness": {"type": "string", "enum": ["complete", "partial", "missing"]},
    "disclaimer_tr": {"type": "string"},
    "prompt_versions": {"type": "object", "additionalProperties": {"type": "string"}}
  },
  "required": ["decision_id", "portfolio_id", "ticker", "action", "confidence", "evidence", "evidence_count", "compliance_status", "effective_at", "created_at", "data_completeness", "disclaimer_tr"],
  "additionalProperties": false
}
```

## Usage

- **Source of truth:** `schemas/decision_record.json`
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
