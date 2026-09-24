# 09 — JSON Schema Standards

> All schemas follow JSON Schema 2020-12. Source of truth: `schemas/` directory. Pydantic models are generated from these via `datamodel-code-generator`.

## 1. Universal Conventions

- **Version:** JSON Schema 2020-12
- **Format:** snake_case for property names
- **Dates:** ISO 8601 with timezone (`2026-07-28T10:30:00+03:00`)
- **Monetary:** `number` in TRY (float); suffix `_usd`/`_eur` for foreign currencies
- **Percentages:** `number` in [0, 1] (0.05 = 5%)
- **Enums:** UPPER_SNAKE_CASE strings
- **Nulls:** `null` allowed where data may be missing (never use empty string)
- **IDs:** UUID v4 (strings)
- **Required:** every schema must declare `required` array
- **Additional properties:** `false` (strict)

## 2. Common Sub-Schemas (reusable)

### `money.json`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "amount": {"type": "number"},
    "currency": {"type": "string", "enum": ["TRY", "USD", "EUR"]}
  },
  "required": ["amount", "currency"]
}
```

### `timestamp.json`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "string",
  "format": "date-time",
  "description": "ISO 8601 with timezone"
}
```

### `ticker.json`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "string",
  "pattern": "^[A-Z]{4,5}$",
  "description": "BIST ticker code (4-5 uppercase letters)"
}
```

### `evidence.json`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "stream": {"type": "string", "enum": ["TECHNICAL", "FUNDAMENTAL", "MACRO", "NEWS", "SENTIMENT", "SECTOR", "PORTFOLIO", "RISK", "SIMILARITY"]},
    "signal": {"type": "string", "enum": ["BULLISH", "BEARISH", "NEUTRAL"]},
    "strength": {"type": "number", "minimum": 0, "maximum": 1},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "source_id": {"type": "string"},
    "source_url": {"type": "string", "format": "uri"},
    "retrieved_at": {"$ref": "timestamp.json"}
  },
  "required": ["stream", "signal", "strength", "confidence", "source_id", "retrieved_at"]
}
```

## 3. Schema Validation Rules

- Every Kafka/Redis message is validated against its schema before consumption.
- Every LLM JSON output is validated before being written to DB.
- Validation failures route to DLQ + alert.
- Schema changes require migration entry in `10-database/05-migrations.md`.

## 4. Schema Naming

- File: `{entity_name}.json` (snake_case)
- `$id`: `https://finance-ai-v3/schemas/{entity_name}.json`
- Title: PascalCase (`DecisionRecord`)

## 5. Backward Compatibility

- Adding optional fields: minor version bump (v1.1)
- Removing fields: major version bump (v2.0) — requires migration
- Renaming fields: major version bump — requires migration
- Changing types: major version bump — requires migration
