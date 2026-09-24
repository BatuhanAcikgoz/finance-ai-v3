# 18/02 — Project Layout

(see `05-folder-structure.md` for full layout)

## Rules

1. **One bounded context per service** under `services/`
2. **Schema-first** — define in `schemas/`, generate models
3. **No circular imports** — use dependency injection
4. **No business logic in `main.py`** — only app setup
5. **No `utils.py` dumping ground** — split into focused modules
6. **Tests mirror source structure** — `tests/unit/{service}/test_{module}.py`

## Service Anatomy (recap)

```
services/{name}/
├── src/{name}/
│   ├── __init__.py
│   ├── client.py        # External API client
│   ├── handlers.py      # Event handlers
│   ├── models.py        # Pydantic (generated)
│   ├── service.py       # Business logic
│   ├── repository.py    # DB access
│   ├── config.py        # pydantic-settings
│   └── main.py          # FastAPI app
├── tests/
├── pyproject.toml
└── Dockerfile
```
