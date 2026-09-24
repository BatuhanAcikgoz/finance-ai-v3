# 05 — Folder Structure

> Monorepo layout. Single `git` repository. `uv` for Python dependency management. `pnpm` workspace for JS/TS.

---

## 1. Root Layout

```
finance-ai-v3/
├── apps/                          # Deployable applications
│   ├── dashboard/                 # Next.js 14 dashboard (TypeScript)
│   │   ├── app/                   # App Router pages
│   │   ├── components/            # React components
│   │   ├── lib/                   # Client-side utilities
│   │   ├── public/                # Static assets
│   │   ├── package.json
│   │   └── tsconfig.json
│   └── api-gateway/               # FastAPI gateway (auth, rate limit, routing)
│       ├── src/
│       │   ├── main.py
│       │   ├── routes/
│       │   ├── middleware/
│       │   └── config.py
│       ├── pyproject.toml
│       └── Dockerfile
│
├── services/                      # Internal service modules (one per bounded context)
│   ├── market_collector/          # BIST ingestion
│   │   ├── src/market_collector/
│   │   │   ├── __init__.py
│   │   │   ├── client.py          # BIST API client
│   │   │   ├── handlers.py        # Event handlers
│   │   │   ├── models.py          # Pydantic models (generated from schemas)
│   │   │   └── service.py         # Business logic
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   ├── tefas_collector/
│   ├── kap_collector/
│   ├── news_collector/
│   ├── macro_collector/
│   ├── technical_analysis/
│   ├── fundamental_analysis/
│   ├── macro_analysis/
│   ├── news_analysis/
│   ├── sentiment_analysis/
│   ├── sector_analysis/
│   ├── risk_engine/
│   ├── portfolio_engine/
│   ├── decision_engine/
│   ├── report_generator/
│   ├── notification_dispatch/
│   ├── backtest_runner/
│   ├── memory_indexer/
│   └── compliance_checker/
│
├── agents/                        # AI agent definitions
│   ├── supervisor/
│   │   ├── prompt.md              # System prompt
│   │   ├── tools.py               # Available tools
│   │   ├── config.yaml            # Model, temperature, max tokens
│   │   └── tests/
│   ├── technical/
│   ├── fundamental/
│   ├── macro/
│   ├── news/
│   ├── sentiment/
│   ├── sector/
│   ├── risk/
│   ├── portfolio/
│   ├── backtest/
│   ├── compliance/
│   ├── memory/
│   └── report/
│
├── workflows/                     # n8n workflow JSON exports + Python step implementations
│   ├── 01_scheduler.json
│   ├── 02_market_collector.json
│   ├── 03_kap_collector.json
│   ├── 04_tefas_collector.json
│   ├── 05_news_collector.json
│   ├── 06_macro_collector.json
│   ├── 07_technical_analysis.json
│   ├── 08_fundamental_analysis.json
│   ├── 09_macro_analysis.json
│   ├── 10_news_analysis.json
│   ├── 11_sentiment_analysis.json
│   ├── 12_sector_analysis.json
│   ├── 13_risk_assessment.json
│   ├── 14_portfolio_analysis.json
│   ├── 15_decision_engine.json
│   ├── 16_report_generation.json
│   ├── 17_notification_dispatch.json
│   ├── 18_backtest_runner.json
│   ├── 19_memory_indexer.json
│   ├── 20_compliance_check.json
│   └── steps/                     # Python step implementations called by n8n
│       ├── __init__.py
│       ├── common.py              # Shared step utilities (auth, logging, retries)
│       └── transforms.py
│
├── schemas/                       # JSON Schema source of truth
│   ├── common/                    # Reusable sub-schemas
│   │   ├── money.json
│   │   ├── timestamp.json
│   │   ├── ticker.json
│   │   └── evidence.json
│   ├── market_data.json
│   ├── news_article.json
│   ├── kap_announcement.json
│   ├── tefas_fund.json
│   ├── analysis_result.json
│   ├── risk_assessment.json
│   ├── portfolio_state.json
│   ├── decision_record.json
│   ├── alert_event.json
│   └── report_payload.json
│
├── prompts/                       # Prompt library (versioned)
│   ├── _shared/                   # Snippets reused across prompts
│   │   ├── turkish_market_context.md
│   │   ├── output_format.md
│   │   └── guardrails.md
│   ├── supervisor_v1.md
│   ├── technical_v1.md
│   ├── fundamental_v1.md
│   ├── macro_v1.md
│   ├── news_v1.md
│   ├── sentiment_v1.md
│   ├── sector_v1.md
│   ├── risk_v1.md
│   ├── portfolio_v1.md
│   ├── backtest_v1.md
│   ├── compliance_v1.md
│   ├── memory_v1.md
│   └── report_v1.md
│
├── infra/                         # Infrastructure as code
│   ├── docker/
│   │   ├── docker-compose.yml     # Dev + staging
│   │   ├── docker-compose.prod.yml
│   │   └── Dockerfile.base
│   ├── k8s/                       # Production k8s manifests
│   │   ├── namespace.yaml
│   │   ├── deployments/
│   │   ├── services/
│   │   ├── ingress/
│   │   ├── configmaps/
│   │   └── secrets/               # Sealed-secrets (encrypted)
│   ├── terraform/                 # Cloud infra (VPC, DB, etc.)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── vault/                     # Vault policies + secret definitions
│       ├── policies/
│       └── secrets.yaml
│
├── tests/                         # Cross-service tests
│   ├── unit/                      # Service-level unit tests
│   ├── integration/               # Cross-service tests with testcontainers
│   ├── e2e/                       # Playwright tests for dashboard
│   ├── load/                      # k6 scripts
│   ├── ai_eval/                   # Promptfoo + DeepEval suites
│   ├── fixtures/                  # Test data (anonymized)
│   │   ├── kap_samples/
│   │   ├── news_samples/
│   │   └── price_samples/
│   └── conftest.py
│
├── scripts/                       # Operational scripts
│   ├── bootstrap.sh               # First-time setup
│   ├── seed_dev_data.py           # Populate dev DB with sample data
│   ├── run_backfill.py            # Backfill historical data
│   ├── backup.sh
│   ├── restore.sh
│   └── rotate_keys.sh
│
├── docs/                          # This documentation set (the 19 files)
│   ├── 00-master-prompt.md
│   ├── 01-product-vision.md
│   ├── ...
│   └── 19-roadmap.md
│
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Lint + test + build on every PR
│       ├── cd.yml                 # Deploy on merge to main
│       ├── security.yml           # SAST + dependency scan
│       └── prompt-regression.yml  # AI eval suite on prompt changes
│
├── .env.example                   # Documented env vars
├── pyproject.toml                 # uv workspace root
├── pnpm-workspace.yaml
├── package.json                   # JS/TS root
├── Makefile                       # Common dev commands
├── README.md
└── LICENSE

```

## 2. Naming Conventions

| Type                | Convention                          | Example                            |
|---------------------|-------------------------------------|------------------------------------|
| Python module       | snake_case                          | `market_collector`                 |
| Python class        | PascalCase                          | `BISTTickClient`                   |
| Python function     | snake_case                          | `fetch_intraday_ticks`             |
| TypeScript file     | kebab-case                          | `market-data-table.tsx`            |
| React component     | PascalCase                          | `DecisionDetailCard`               |
| JSON Schema file    | snake_case.json                     | `decision_record.json`             |
| n8n workflow file   | `{NN}_{snake_case}.json`            | `02_market_collector.json`         |
| Prompt file         | `{agent}_v{N}.md`                   | `technical_v1.md`                  |
| Database table      | snake_case, plural                  | `kap_disclosures`                  |
| Database column     | snake_case                          | `published_at`                     |
| Redis key           | colon-separated, lowercase          | `tick:thyo:latest`                 |
| Qdrant collection   | snake_case                          | `news_embeddings`                  |
| Docker image        | lowercase, kebab-case               | `finance-ai-v3/market-collector`   |
| Environment variable| UPPER_SNAKE_CASE                    | `BIST_API_KEY`                     |

## 3. Module Anatomy

Every service under `services/` follows this layout:

```
services/{name}/
├── src/{name}/
│   ├── __init__.py            # Public API
│   ├── client.py              # External API client (if any)
│   ├── handlers.py            # Event handlers (Redis subscribers)
│   ├── models.py              # Pydantic models (generated from schemas/)
│   ├── service.py             # Business logic
│   ├── repository.py          # Database access (asyncpg)
│   ├── config.py              # pydantic-settings
│   └── main.py                # FastAPI app (if exposes HTTP)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_client.py
│   ├── test_service.py
│   └── test_handlers.py
├── pyproject.toml             # uv project file
└── Dockerfile
```

## 4. Schema-First Code Generation

Schemas in `schemas/` are the source of truth. Pydantic models are generated via:

```bash
make generate-models
# Internally runs:
# datamodel-code-generator --input schemas/decision_record.json \
#   --output services/decision_engine/src/decision_engine/models.py
```

Generated files carry a header: `# AUTO-GENERATED. DO NOT EDIT. Modify schemas/decision_record.json and re-run.`

## 5. Git Rules

- Trunk-based: short-lived branches, ≤ 3 days.
- Branch naming: `{type}/{FR-id or slug}` — e.g. `feat/FR-001-bist-tick-ingest`.
- Conventional Commits required: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`.
- Squash-and-merge.
- Every PR must reference at least one FR ID in its description.

## 6. Makefile Targets

```makefile
.PHONY: install dev test lint type-check generate-models docker-up docker-down

install:
    uv sync
    pnpm install

dev:
    docker compose -f infra/docker/docker-compose.yml up -d
    uv run uvicorn apps.api-gateway.src.main:app --reload
    pnpm --filter dashboard dev

test:
    uv run pytest tests/

lint:
    uv run ruff check .
    uv run ruff format --check .
    pnpm --filter dashboard lint

type-check:
    uv run mypy --strict services/ apps/
    pnpm --filter dashboard type-check

generate-models:
    ./scripts/generate_models.sh

docker-up:
    docker compose -f infra/docker/docker-compose.yml up -d --build

docker-down:
    docker compose -f infra/docker/docker-compose.yml down
```
