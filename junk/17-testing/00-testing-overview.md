# 17 — Testing Overview

> Test pyramid: 70% unit, 20% integration, 10% e2e. Plus AI eval, load, and chaos.

## Test Types

| Type          | Tool             | Frequency       | Coverage target |
|---------------|------------------|-----------------|-----------------|
| Unit          | pytest           | Every PR        | ≥ 80% per service |
| Integration   | testcontainers   | Every PR        | 100% pass       |
| E2E           | Playwright       | Daily + on PR   | Critical paths  |
| AI Eval       | promptfoo + DeepEval | Every prompt PR | ≥ 0.85 pass    |
| Load          | k6               | Weekly          | p95 < 2s        |
| Chaos         | custom scripts   | Monthly         | Recovery < 5min |
| Data Quality  | Great Expectations | Daily         | 100% pass       |

## CI Pipeline

```yaml
# .github/workflows/ci.yml (simplified)
jobs:
  lint:
    runs-on: ubuntu-latest
    steps: [run: uv run ruff check ., run: uv run ruff format --check .]
  
  type-check:
    runs-on: ubuntu-latest
    steps: [run: uv run mypy --strict services/ apps/]
  
  unit-tests:
    runs-on: ubuntu-latest
    steps: [run: uv run pytest tests/unit/ --cov --cov-fail-under=80]
  
  integration-tests:
    runs-on: ubuntu-latest
    services: {postgres, redis, qdrant}
    steps: [run: uv run pytest tests/integration/]
  
  e2e-tests:
    runs-on: ubuntu-latest
    steps: [run: pnpm --filter dashboard playwright test]
  
  ai-eval:
    runs-on: ubuntu-latest
    if: contains(github.event.head_commit.modified, 'prompts/')
    steps: [run: uv run promptfoo eval --config tests/ai_eval/promptfoo.yaml]
  
  security:
    runs-on: ubuntu-latest
    steps:
      - run: uv run bandit -r services/
      - run: uv run pip-audit
      - run: trufflehog filesystem .
```
