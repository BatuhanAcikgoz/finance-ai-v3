# 09/01 — Market Data Schema

> **Description:** Market data: ticks, bars, indices, macro indicators

## Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://finance-ai-v3/schemas/market_data.json",
  "title": "MarketData",
  "type": "object",
  "oneOf": [
    {"$ref": "#/$defs/Tick"},
    {"$ref": "#/$defs/Bar"},
    {"$ref": "#/$defs/IndexValue"},
    {"$ref": "#/$defs/MacroIndicator"}
  ],
  "$defs": {
    "Tick": {
      "type": "object",
      "properties": {
        "ticker": {"$ref": "ticker.json"},
        "price": {"type": "number", "minimum": 0},
        "volume": {"type": "number", "minimum": 0},
        "bid": {"type": "number", "minimum": 0},
        "ask": {"type": "number", "minimum": 0},
        "exchange_timestamp": {"$ref": "timestamp.json"},
        "source": {"type": "string", "enum": ["BIST_API", "BIST_WS"]}
      },
      "required": ["ticker", "price", "volume", "exchange_timestamp", "source"],
      "additionalProperties": false
    },
    "Bar": {
      "type": "object",
      "properties": {
        "ticker": {"$ref": "ticker.json"},
        "timeframe": {"type": "string", "enum": ["1m", "5m", "15m", "60m", "1d"]},
        "open": {"type": "number"},
        "high": {"type": "number"},
        "low": {"type": "number"},
        "close": {"type": "number"},
        "volume": {"type": "number", "minimum": 0},
        "bar_start": {"$ref": "timestamp.json"},
        "bar_end": {"$ref": "timestamp.json"}
      },
      "required": ["ticker", "timeframe", "open", "high", "low", "close", "volume", "bar_start", "bar_end"],
      "additionalProperties": false
    },
    "IndexValue": {
      "type": "object",
      "properties": {
        "index_code": {"type": "string", "pattern": "^BIST-[A-Z]{3,}$|^XU100$"},
        "value": {"type": "number", "minimum": 0},
        "change_pct": {"type": "number"},
        "as_of": {"$ref": "timestamp.json"}
      },
      "required": ["index_code", "value", "as_of"],
      "additionalProperties": false
    },
    "MacroIndicator": {
      "type": "object",
      "properties": {
        "indicator_code": {"type": "string"},
        "source": {"type": "string", "enum": ["TCMB", "TUIKS", "BDDK"]},
        "value": {"type": "number"},
        "unit": {"type": "string"},
        "release_date": {"type": "string", "format": "date"},
        "revised_from": {"type": ["number", "null"]}
      },
      "required": ["indicator_code", "source", "value", "unit", "release_date"],
      "additionalProperties": false
    }
  }
}
```

## Usage

- **Source of truth:** `schemas/market_data.json`
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
