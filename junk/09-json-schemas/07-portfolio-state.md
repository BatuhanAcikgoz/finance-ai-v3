# 09/07 — Portfolio State Schema

> **Description:** Portfolio holdings + target weights

## Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://finance-ai-v3/schemas/portfolio_state.json",
  "title": "PortfolioState",
  "type": "object",
  "properties": {
    "portfolio_id": {"type": "string"},
    "user_id": {"type": "string"},
    "as_of": {"$ref": "timestamp.json"},
    "total_value_try": {"type": "number", "minimum": 0},
    "holdings": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "ticker": {"$ref": "ticker.json"},
          "shares": {"type": "number", "minimum": 0},
          "current_price": {"type": "number", "minimum": 0},
          "current_value_try": {"type": "number", "minimum": 0},
          "current_weight": {"type": "number", "minimum": 0, "maximum": 1},
          "target_weight": {"type": "number", "minimum": 0, "maximum": 1},
          "cost_basis_try": {"type": "number"},
          "unrealized_pnl_try": {"type": "number"}
        },
        "required": ["ticker", "shares", "current_price", "current_value_try", "current_weight"]
      }
    },
    "constraints": {
      "type": "object",
      "properties": {
        "max_position_pct": {"type": "number", "default": 0.25},
        "max_sector_pct": {"type": "number", "default": 0.40},
        "max_portfolio_var_pct": {"type": "number", "default": 0.03}
      }
    }
  },
  "required": ["portfolio_id", "user_id", "as_of", "total_value_try", "holdings"],
  "additionalProperties": false
}
```

## Usage

- **Source of truth:** `schemas/portfolio_state.json`
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
