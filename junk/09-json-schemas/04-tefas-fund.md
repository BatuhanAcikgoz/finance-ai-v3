# 09/04 — Tefas Fund Schema

> **Description:** TEFAS fund NAV and flow

## Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://finance-ai-v3/schemas/tefas_fund.json",
  "title": "TefasFund",
  "type": "object",
  "properties": {
    "fund_code": {"type": "string", "pattern":^[A-Z]{3}$"},
    "fund_name": {"type": "string"},
    "fund_type": {"type": "string", "enum": ["MUTUAL", "PARTICIPATION", "GOLD", "INDEX", "BOND", "PENSION"]},
    "nav": {"type": "number", "minimum": 0},
    "nav_date": {"type": "string", "format": "date"},
    "daily_return_pct": {"type": "number"},
    "ytd_return_pct": {"type": "number"},
    "flow_subscription_try": {"type": "number", "minimum": 0},
    "flow_redemption_try": {"type": "number", "minimum": 0},
    "net_flow_try": {"type": "number"},
    "total_assets_try": {"type": "number", "minimum": 0},
    "investor_count": {"type": "integer", "minimum": 0},
    "ingested_at": {"$ref": "timestamp.json"}
  },
  "required": ["fund_code", "fund_name", "fund_type", "nav", "nav_date", "ingested_at"],
  "additionalProperties": false
}
```

## Usage

- **Source of truth:** `schemas/tefas_fund.json`
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
