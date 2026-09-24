# 17/05 — AI Eval Tests

## Tools

- **promptfoo:** prompt regression testing
- **DeepEval:** LLM output quality (faithfulness, hallucination)
- **Custom:** Turkish market-specific assertions

## Test Cases per Agent

| Agent        | Test cases | What we test                                |
|--------------|------------|---------------------------------------------|
| Technical    | 50         | Correct signal direction, indicator citation |
| Fundamental  | 50         | Number extraction accuracy, ratio correctness |
| Macro        | 30         | Surprise computation, regime detection       |
| News         | 100        | Ticker extraction, topic classification      |
| Sentiment    | 100        | Sentiment score correlation with human label |
| Sector       | 20         | Rotation detection, return computation       |
| Backtest     | 10         | Hit-rate computation, weight proposal sanity |
| Compliance   | 50         | Forbidden language detection, false positive rate |
| Report       | 20         | Word count, decision citation accuracy       |
| Supervisor   | 30         | Evidence aggregation, INSUFFICIENT_EVIDENCE handling |

## Example (promptfoo)

```yaml
# tests/ai_eval/promptfoo.yaml
description: "Technical agent regression"
prompts:
  - file://prompts/technical_v1.md
providers:
  - id: minimax
    config:
      model: minimax-m3
      temperature: 0.1
tests:
  - vars:
      ticker: THYAO
      indicators:
        rsi_14: 70
        macd: { line: 2.5, signal: 1.8, histogram: 0.7 }
    assert:
      - type: contains-json
        value:
          direction: BULLISH
      - type: javascript
        value: output.confidence > 0.5
      - type: llm-rubric
        value: "Reasoning mentions RSI and MACD"
  
  - vars:
      ticker: THYAO
      indicators: {}
    assert:
      - type: contains-json
        value:
          direction: NEUTRAL
          data_completeness: missing
```

## Run

```bash
uv run promptfoo eval --config tests/ai_eval/promptfoo.yaml
```

## Pass Criteria

- ≥ 85% pass rate per agent
- 100% pass on safety tests (forbidden language, hallucination guards)
