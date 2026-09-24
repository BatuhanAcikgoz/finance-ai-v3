# 18/03 — Git Workflow

## Trunk-Based Development

- `main` is always deployable
- Short-lived feature branches (≤ 3 days)
- Squash-and-merge
- Direct pushes to `main` forbidden
- Force-push to `main` forbidden

## Conventional Commits

```
feat: add BIST tick ingestion (FR-001)
fix: correct VaR computation when window < 60 days
chore: bump LiteLLM to 1.45
refactor: extract confidence scoring to own module
docs: add 17-testing documentation
test: add unit tests for decision engine
```

## PR Template

```markdown
## Description
[What does this PR do?]

## Linked FRs
- FR-XXX

## Type of change
- [ ] feat (new feature)
- [ ] fix (bug fix)
- [ ] refactor
- [ ] docs
- [ ] test
- [ ] chore

## Checklist
- [ ] Code follows style guide (ruff, mypy pass)
- [ ] Tests added / updated
- [ ] Docs updated (if applicable)
- [ ] Schema migration added (if applicable)
- [ ] No secrets in code
- [ ] PR size < 500 lines
```

## Branch Protection Rules

- Require PR review (1 reviewer for non-critical, 2 for critical)
- Require status checks: lint, type-check, unit, integration, e2e
- Require branches up-to-date before merge
- Dismiss stale reviews on push
- Restrict who can push to `main` (admins only)
