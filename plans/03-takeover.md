# Takeover Plan — Docker MVP

## Current state
- Initial commit only, no remote set yet.
- `uv` workspace with 19 services + `apps/api-gateway` + dashboard (Next.js).
- `infra/docker/docker-compose.yml` defines infra (postgres/redis/qdrant/litellm/n8n/prom/grafana/loki/jaeger/otel) but NO app services.
- Most services are scaffold (pyproject + ~5 src files each).
- `gh` logged in as `BatuhanAcikgoz`. `kilo-bin` not on PATH (only `kilocode`/`.kilo/` config dir).
- `apps/dashboard` has node_modules but no Next `app/` or `pages/` directory — `next build` would fail.

## Decision
**Pragmatic MVP, not full 19-service production stack.** Goal: one `docker compose up` brings up a working Turkish-finance research API + a static dashboard, with a real BIST data flow on the happy path.

### What runs for real
1. `infra/docker/docker-compose.yml` — add: postgres, redis, qdrant, otel-collector, prometheus, grafana, jaeger, loki, litellm, n8n, **api-gateway**, **kap-collector**, **technical-analysis**, **decision-engine**, **report-generator**, **nginx (static dashboard)**, **seed** (one-shot).
2. `apps/api-gateway` — FastAPI service: `/health`, `/v1/market/decisions`, `/v1/market/ohlcv/{symbol}`, `/docs`. Real endpoints backed by postgres/qdrant.
3. `services/kap_collector` — pulls KAP public disclosures (KAP has a free CSV feed, no key required: `https://www.kap.org.tr/tr/bildirim-sorgu` plus the per-day CSV). Falls back to a sample generator when offline.
4. `services/technical_analysis` — pandas-ta-lite: RSI/MACD/Bollinger on OHLCV from `market_collector` (which we'll seed from a small synthetic dataset since we have no BIST API key).
5. `services/decision_engine` — combines technical + sentiment (placeholder) + risk score → emits a `Decision` row in postgres.
6. `services/report_generator` — markdown report per decision, stored in `reports/` volume.
7. `apps/dashboard` — converted to a single static HTML+vanilla JS page served by nginx (the Next app has no source, so a static page is honest and runnable).

### What becomes stub-healthy
The other 14 services get a `health.py` returning `{"status":"ok","service":"<name>","mode":"stub"}` and are still wired into docker-compose so the architecture is visible — but they don't process data. This is honest: no fake "decisions" from services that don't exist.

## Mechanics
- Single command: `make up` → `docker compose -f infra/docker/docker-compose.yml up -d --build` + `./scripts/wait_for.sh`.
- Single command teardown: `make down`.
- All `.env` defaults baked in via `.env.docker` so `up` works with no manual config.
- `.env.example` already exists; we add `.env.docker` with safe defaults and `docker/.env` symlink.

## Worktree / branches
Direct work on `main`. After CI passes manually, commit + push + `gh repo create` then push.

## Verification gates (must all pass before commit)
1. `docker compose config` exits 0.
2. `docker compose up -d --build` exits 0 and all services `healthy`.
3. `curl localhost:8000/health` → 200.
4. `curl localhost:8000/v1/market/decisions` → 200 with JSON.
5. `curl localhost:8080/` → 200 with HTML dashboard.
6. `docker logs decision-engine` shows at least one decision written.
7. `make test` (in-container `pytest tests/unit` for shared + api-gateway) exits 0.

## Risks
- Docker build context bloat: uv.lock is 800KB ok, but `services/report_generator` had 122k lines of auto-generated test fixtures. Will exclude via `.dockerignore`.
- KAP scrape blocked from inside container: use the public CSV endpoint that requires no auth.
- Litellm requires master key: provide a default in `.env.docker` with a clear `CHANGE_ME_DEV_ONLY` label.
- Dashboard Next.js build broken: replace with static HTML, mark dashboard as "static preview" in README.

## Out of scope (for this MVP)
- 14 stub-only services doing real work.
- Real LiteLLM provider keys (we'll wire env stubs).
- Vault / k8s / terraform / Vault config (already empty, leave alone).
- Grafana dashboards provisioning (basic blank dashboards only).
