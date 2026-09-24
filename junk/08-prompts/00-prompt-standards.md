# 08 — Prompt Standards

> All prompts in this directory follow these standards. Any deviation requires explicit approval.

## 1. Universal Prompt Anatomy

Every prompt file MUST contain:

1. **Role definition** — who the agent is (1 sentence)
2. **Context** — Turkish market specifics relevant to this agent
3. **Task** — what the agent must do (bullet list)
4. **Input schema reference** — link to `09-json-schemas/`
5. **Output schema** — explicit JSON structure with field types
6. **Rules** — hard constraints (NEVER / ALWAYS)
7. **Few-shot examples** — at least 2 (happy path + edge case)
8. **Failure mode** — what to output if input is bad
9. **Token budget** — max input + output tokens
10. **Model config** — temperature, top_p, max_tokens

## 2. Universal Rules (apply to ALL prompts)

### NEVER
- NEVER fabricate financial data
- NEVER output a ticker that is not in BIST
- NEVER output a number that is not in the input
- NEVER skip the disclaimer
- NEVER exceed max_tokens
- NEVER use markdown in JSON output (raw text only)

### ALWAYS
- ALWAYS output valid JSON (no prose, no markdown fences)
- ALWAYS include `confidence` field in [0, 1]
- ALWAYS include `evidence[]` array (can be empty)
- ALWAYS include `reasoning` field (1-3 sentences, Turkish)
- ALWAYS cite source_id for every claim
- ALWAYS include `data_completeness` field: "complete" | "partial" | "missing"

## 3. JSON Output Discipline

- Top-level object always wrapped in `{}`
- snake_case keys
- ISO 8601 timestamps with timezone (e.g. `2026-07-28T10:30:00+03:00`)
- All monetary values as `float` in TRY unless suffixed `_usd`, `_eur`
- All percentages as `float` in [0, 1] (e.g. 0.05 = 5%)
- All enums in UPPER_SNAKE_CASE

## 4. Turkish Market Context (shared snippet)

Insert this verbatim into every prompt:

```
TURKISH MARKET CONTEXT:
- Trading hours: 10:00–18:00 TRT (Europe/Istanbul, UTC+3), weekdays only
- Pre-open auction: 09:45–10:00
- BIST ticker format: 4-5 uppercase letters (THYAO, GARAN, KCHOL)
- KAP = Kamuyu Aydınlatma Platformu (public disclosure platform)
- TEFAS = Turkish Electronic Fund Trading Platform
- TCMB = Türkiye Cumhuriyet Merkez Bankası (central bank)
- TÜİK = Türkiye İstatistik Kurumu (statistics institute)
- BDDK = Bankacılık Düzenleme ve Denetleme Kurumu (banking regulator)
- All prices in TRY; BIST-100 is the benchmark index
- Holidays: official BIST trading calendar (different from bank holidays)
- Currency: TRY (Turkish Lira), ISO 4217
```

## 5. Token Budgets

| Agent        | Max input tokens | Max output tokens | Temperature |
|--------------|------------------|-------------------|-------------|
| Supervisor   | 8,000            | 1,500             | 0.2         |
| Technical    | 4,000            | 500               | 0.1         |
| Fundamental  | 8,000            | 800               | 0.1         |
| Macro        | 6,000            | 600               | 0.2         |
| News         | 4,000            | 400               | 0.1         |
| Sentiment    | 4,000            | 300               | 0.1         |
| Sector       | 6,000            | 600               | 0.2         |
| Risk         | N/A               | N/A               | N/A         |
| Portfolio    | N/A               | N/A               | N/A         |
| Backtest     | 12,000           | 1,500             | 0.2         |
| Compliance   | 4,000            | 300               | 0.0         |
| Memory       | N/A               | N/A               | N/A         |
| Report       | 8,000            | 2,500             | 0.4         |

## 6. Prompt Versioning

- File naming: `{agent}_v{N}.md`
- Version bump rules:
  - PATCH (v1.0.1): typo fix, clarification
  - MINOR (v1.1.0): new few-shot example, new edge case
  - MAJOR (v2.0.0): schema change, rule change
- Every change logged in `prompts/CHANGELOG.md`
- Old versions retained for A/B testing

## 7. A/B Testing Protocol

- Prompts can be deployed in 50/50 split via `prompts/ab_config.yaml`
- Decision records tag `prompt_version` for attribution
- Backtest compares hit-rate across versions
- Promotion to 100% requires: ≥ 30 decisions + statistically significant improvement

## 8. Forbidden Patterns in Prompts

1. ❌ "Do your best" — vague, unmeasurable
2. ❌ "Be careful" — without specific constraint
3. ❌ "Think step by step" — use chain-of-thought structure explicitly if needed
4. ❌ "You are an expert" — define expertise by task, not by title
5. ❌ Multiple conflicting rules — pick one
6. ❌ Rules without enforcement — every rule must have a quality check

## 9. Required Patterns

1. ✅ Explicit output JSON schema
2. ✅ Few-shot examples
3. ✅ Failure mode (what to output if input is bad)
4. ✅ Citation requirement
5. ✅ Confidence field requirement
