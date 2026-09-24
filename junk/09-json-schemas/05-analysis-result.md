# 09/05 — Analysis Result Schema

> **Description:** Analysis result from any agent (8 subtypes via oneOf)

## Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://finance-ai-v3/schemas/analysis_result.json",
  "title": "AnalysisResult",
  "type": "object",
  "oneOf": [
    {"$ref": "#/$defs/TechnicalSignal"},
    {"$ref": "#/$defs/FundamentalSignal"},
    {"$ref": "#/$defs/MacroSignal"},
    {"$ref": "#/$defs/NewsAnalysis"},
    {"$ref": "#/$defs/SentimentAnalysis"},
    {"$ref": "#/$defs/SectorAnalysis"}
  ],
  "$defs": {
    "TechnicalSignal": {
      "type": "object",
      "properties": {
        "ticker": {"$ref": "ticker.json"},
        "direction": {"type": "string", "enum": ["BULLISH", "BEARISH", "NEUTRAL"]},
        "strength": {"type": "number", "minimum": 0, "maximum": 1},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "indicators_referenced": {"type": "array", "items": {"type": "object"}},
        "reasoning": {"type": "string"},
        "data_completeness": {"type": "string", "enum": ["complete", "partial", "missing"]}
      },
      "required": ["ticker", "direction", "strength", "confidence", "data_completeness"]
    },
    "FundamentalSignal": {"type": "object", "description": "see 08-prompts/03-fundamental-prompt.md"},
    "MacroSignal": {"type": "object", "description": "see 08-prompts/04-macro-prompt.md"},
    "NewsAnalysis": {"type": "object", "description": "see 08-prompts/05-news-prompt.md"},
    "SentimentAnalysis": {"type": "object", "description": "see 08-prompts/06-sentiment-prompt.md"},
    "SectorAnalysis": {"type": "object", "description": "see 08-prompts/07-sector-prompt.md"}
  }
}
```

## Usage

- **Source of truth:** `schemas/analysis_result.json`
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
