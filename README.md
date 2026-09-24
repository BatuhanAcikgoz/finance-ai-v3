# Finance AI V3

> **Autonomous financial research analyst for Turkish capital markets (BIST).**
> A multi-agent system that ingests market data, news, KAP disclosures, and macro
> signals to produce auditable, evidence-backed trade decisions for a Turkish
> portfolio.

---

## Architecture

```
                          ┌────────────────────────────┐
                          │        Browser (UI)        │
                          │ apps/dashboard/dist/       │
                          │   static HTML + vanilla JS │
                          └──────────────┬─────────────┘
                                         │ /api/* + /
                                         ▼
                          ┌────────────────────────────┐
                          │       Nginx (reverse proxy)│
                          │       port 8080            │
                          └──┬──────────────────────┬──┘
                             │ /                   │ /api/*
                             ▼                     ▼
                ┌────────────────────┐   ┌──────────────────────┐
                │   Static Dashboard │   │   api-gateway        │
                │   apps/dashboard/  │   │   FastAPI · port 8000│
                │   dist/            │   └──┬─────────┬────────┘
                └────────────────────┘      │         │
                                            ▼         ▼
                          ┌─────────────┐    ┌──────────────┐
                          │ PostgreSQL  │    │  Redis       │
                          │   :5432     │    │  :6379       │
                          └─────────────┘    └──────────────┘
                                                    │
                          ┌─────────────────────────┴───┐
                          │   4 active Python workers   │
                          │  market_collector           │
                          │  decision_engine            │
                          │  (2 more — see Services)    │
                          └─────────────────────────────┘

              Observability: Prometheus · Grafana · Loki · Jaeger · OTel
              Auxiliary:      Qdrant (vector store) · LiteLLM · n8n
```

## Quick start

```bash
# 1. Copy the docker env template (one-time)
cp infra/docker/.env.docker infra/docker/.env || true

# 2. Bring the stack up
make up

# 3. Open the dashboard
open http://localhost:8080
```

`make up` builds and starts Docker Compose, waits for healthchecks, then prints
the URLs for the dashboard, API, n8n, Grafana, etc.

## What's running

| Service           | Port  | Image / Stack         | Role                            |
|-------------------|-------|-----------------------|---------------------------------|
| **nginx**         | 8080  | `nginx:alpine`        | reverse proxy + static dashboard|
| **api-gateway**   | 8000  | FastAPI · Python 3.12 | single REST entrypoint          |
| **postgres**      | 5432  | `postgres:16-alpine`  | primary store                   |
| **redis**         | 6379  | `redis:7-alpine`      | cache + pub/sub bus             |
| **qdrant**        | 6333  | `qdrant/qdrant:v1.10` | vector store (news, KAP)        |
| **prometheus**    | 9090  | `prom/prometheus`     | metrics                         |
| **grafana**       | 3001  | `grafana/grafana`     | dashboards                      |
| **loki**          | 3100  | `grafana/loki`        | logs                            |
| **jaeger**        | 16686 | `jaegertracing/all-in-one` | traces                      |
| **otel-collector**| 4317  | `otel/opentelemetry-collector` | OTLP receiver         |

## Service modes

This repo currently mixes **real** and **stub** services. The split is intentional
while the long-running workers are scaffolded:

### Real (4)
- `api-gateway`           — FastAPI gateway, health + v1 routes wired.
- `market_collector`      — pulls BIST tick data into Redis.
- `decision_engine`       — consolidates signals into BUY/SELL/HOLD decisions.
- *(+ a fourth worker — see `services/` for the latest active set)*

### Stub (14)
The remaining service directories (`news_collector`, `kap_collector`,
`tefas_collector`, `macro_collector`, `risk_engine`, `portfolio_engine`,
`report_generator`, `notification_dispatch`, `compliance_agent`,
`memory_agent`, `fundamental_analysis`, `technical_analysis`,
`sentiment_analysis`, `sector_analysis`, `backtest_agent`,
`macro_analysis`, `news_analysis`) are scaffolded with package manifests and
tests but **not yet deployed** as containers. They're listed in `services/`
and their specs are tracked in `docs/`.

## Development

```bash
# install Python + Node deps
uv sync
pnpm install

# run API tests (with coverage gate)
make test          # or: uv run pytest tests/ -v

# lint + format
make lint          # ruff
make fmt           # ruff format
make type-check    # mypy --strict

# generate Pydantic models from JSON schemas
make generate-models
```

## MVP scope

| Capability                              | Status |
|-----------------------------------------|--------|
| Postgres + Redis + Qdrant infra         | ✅ real |
| FastAPI gateway with health + routes    | ✅ real |
| Static dashboard (this repo)            | ✅ real |
| Market data ingestion                   | ✅ real (1 worker) |
| Decision engine core                    | ✅ real (1 worker) |
| News / KAP / macro ingestion            | 🚧 stub |
| Portfolio + risk + report workers       | 🚧 stub |
| End-to-end backtests                    | 🚧 stub |
| Production auth + multi-tenant         | ❌ not in MVP |

## Roadmap

- Bring remaining 4 workers online (news, KAP, technical, risk) — target end of MVP phase 1.
- Replace api-gateway stub routes (`/v1/market/symbols`, `/v1/decisions/recent`) with live data.
- WebSocket tick stream in dashboard for intraday view.
- Evals + backtest suite with deterministic replay fixtures.
- K8s manifests under `infra/k8s/` already stubbed — promote to production target.

---

© Finance AI V3 — built with FastAPI · Postgres · Redis · Qdrant · LiteLLM · n8n.
