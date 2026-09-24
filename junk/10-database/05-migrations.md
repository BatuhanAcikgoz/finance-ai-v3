# 10/05 — Migration Strategy

> Tool: `alembic`. Migrations are versioned, reversible, and reviewed.

## Migration File Naming

`V{YYYYMMDDHHMM}__{description}.sql` or `.py`

Examples:
- `V202607281200__initial_schema.py`
- `V202608011500__add_decision_compliance_reason.py`
- `V202608101000__add_qdrant_decision_memory_collection.py`

## Rules

1. **Reversible:** every migration must have `up()` and `down()`
2. **Tested:** must pass on staging before production
3. **Reviewed:** DBA review required for schema changes
4. **Documented:** description in migration file + entry in this file
5. **Atomic:** single transaction per migration

## Migration Log

| Version       | Description                                        | Date       | Reversible |
|---------------|----------------------------------------------------|------------|------------|
| V202607281200 | Initial schema (all core tables)                   | 2026-07-28 | Yes        |
| V202608011500 | Add compliance_reason column to decisions          | 2026-08-01 | Yes        |
| V202608051000 | Add Qdrant decision_memory collection              | 2026-08-05 | Yes        |
| V202608101200 | Add backtest.weight_adjustments_proposed JSONB     | 2026-08-10 | Yes        |
| V202608151500 | Add news.article_tickers table                     | 2026-08-15 | Yes        |

## Procedure

```bash
# Generate empty migration
uv run alembic revision -m "description"

# Apply
uv run alembic upgrade head

# Rollback one
uv run alembic downgrade -1

# Show status
uv run alembic current
uv run alembic history
```
