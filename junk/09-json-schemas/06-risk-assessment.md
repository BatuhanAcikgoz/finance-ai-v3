# 09/06 — Risk Assessment Schema

> **Description:** Portfolio risk metrics

## Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://finance-ai-v3/schemas/risk_assessment.json",
  "title": "RiskAssessment",
  "type": "object",
  "properties": {
    "assessment_id": {"type": "string", "format": "uuid"},
    "portfolio_id": {"type": "string"},
    "as_of_date": {"$ref": "timestamp.json"},
    "var_1d_95": {"type": "number"},
    "cvar_1d_95": {"type": "number"},
    "beta_to_bist100": {"type": "number"},
    "tracking_error_1y": {"type": "number", "minimum": 0},
    "hhi_concentration": {"type": "number", "minimum": 0, "maximum": 1},
    "sector_exposures": {"type": "object", "additionalProperties": {"type": "number"}},
    "style_exposures": {
      "type": "object",
      "properties": {"value": {"type": "number"}, "growth": {"type": "number"}, "quality": {"type": "number"}}
    },
    "risk_budget_pct": {"type": "number", "minimum": 0},
    "risk_budget_exceeded": {"type": "boolean"},
    "data_completeness": {"type": "string", "enum": ["complete", "partial", "missing"]}
  },
  "required": ["assessment_id", "portfolio_id", "as_of_date", "var_1d_95", "cvar_1d_95", "beta_to_bist100", "hhi_concentration", "risk_budget_exceeded", "data_completeness"],
  "additionalProperties": false
}
```

## Usage

- **Source of truth:** `schemas/risk_assessment.json`
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
