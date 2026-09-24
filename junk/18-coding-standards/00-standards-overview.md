# 18 — Coding Standards Overview

> Standards are enforced by tooling, not just docs. CI fails on violations.

## Tooling

| Tool          | Purpose                          | Config file          |
|---------------|----------------------------------|----------------------|
| ruff          | Lint + format (replaces black + flake8 + isort) | `pyproject.toml` |
| mypy          | Static type checking (strict)    | `pyproject.toml`     |
| bandit        | Security lint                    | `.bandit`            |
| pip-audit     | Dependency vulnerability scan   | (no config)          |
| trufflehog    | Secrets scan                     | `.trufflehogignore`  |
| eslint        | JS/TS lint                       | `eslint.config.js`   |
| prettier      | JS/TS format                     | `.prettierrc`        |
| typescript    | Type check                       | `tsconfig.json`      |

## Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, sqlalchemy]
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.9
    hooks:
      - id: bandit
        args: [-c, .bandit]
  - repo: https://github.com/trufflesecurity/trufflehog
    rev: v3.78.0
    hooks:
      - id: trufflehog
```
