# Phase 1 MVP Implementation Plan
## Finance AI V3 — FR-001 to FR-025
**Target:** End-to-end proof-of-concept with THYAO ticker (8 weeks)

---

## Executive Summary

Phase 1 MVP proves the data pipeline end-to-end with a single ticker (THYAO). By Week 8, the system will:
- Ingest BIST tick data in real-time (< 2s latency)
- Process KAP disclosures within 5 minutes
- Compute 40+ technical indicators
- Send daily briefing email by 08:30 TRT
- Display live data on dashboard skeleton

---

## Architecture Overview

```
Week 1-2 (Infrastructure)
┌─────────────────────────────────────────────┐
│  Docker Compose: PostgreSQL + Redis + Qdrant │
│  Project scaffolding: uv, pnpm, Makefile     │
│  CI/CD: GitHub Actions                       │
│  JSON Schemas: Pydantic model generation     │
└─────────────────────────────────────────────┘
           │
Week 3-5 (Data Ingestion)
           ▼
┌─────────────────────────────────────────────┐
│  market_collector  →  BIST tick/bar data   │
│  kap_collector     →  KAP disclosures       │
│  news_collector    →  News from 12 sources  │
│  macro_collector   →  TCMB/TÜİK indicators  │
└─────────────────────────────────────────────┘
           │
Week 6-8 (Analysis + Output)
           ▼
┌─────────────────────────────────────────────┐
│  technical_analysis → 40+ indicators        │
│  report_generator   → Morning/Evening email │
│  dashboard (skeleton) → Live price + alerts  │
└─────────────────────────────────────────────┘
```

---

## Week-by-Week Breakdown

### Week 1: Project Scaffolding
**Goal:** Foundation ready for development

| Task | Deliverable | Files Created |
|------|-------------|---------------|
| 1.1 Create monorepo structure | `apps/`, `services/`, `workflows/`, `schemas/`, `agents/`, `infra/`, `tests/` | `pyproject.toml`, `pnpm-workspace.yaml`, `package.json` |
| 1.2 Set up `uv` for Python | Python 3.12+, dependencies | `pyproject.toml` per service |
| 1.3 Set up `pnpm` for TypeScript | Next.js dashboard ready | `package.json` for dashboard |
| 1.4 Create Docker Compose | PostgreSQL 16, Redis 7, Qdrant 1.10 | `infra/docker/docker-compose.yml` |
| 1.5 Create `Makefile` | `make install`, `make dev`, `make test` | `Makefile` |
| 1.6 Set up GitHub Actions CI | Lint + test + type-check on PR | `.github/workflows/ci.yml` |
| 1.7 Create JSON Schema files | Tick, Bar, Index, News, KAP schemas | `schemas/01-market-data.json`, `schemas/02-news-article.json`, `schemas/03-kap-announcement.json` |
| 1.8 Create Pydantic model generator | `make generate-models` | `scripts/generate_models.sh` |
| 1.9 Create `.env.example` | All required env vars documented | `.env.example` |

**Files Created:** ~25 new files
**Testing:** `make lint && make type-check && make test`

---

### Week 2: Database Infrastructure
**Goal:** PostgreSQL + Redis + Qdrant running with schemas applied

| Task | Deliverable | Files Created |
|------|-------------|---------------|
| 2.1 Apply PostgreSQL schema | All tables from `10-database/01-postgres-schema.md` | `services/shared/migrations/` |
| 2.2 Create Alembic migrations | Versioned schema migrations | `services/shared/migrations/versions/` |
| 2.3 Set up Redis key patterns | Keys from `10-database/02-redis-keys.md` | `infra/docker/redis.conf` |
| 2.4 Configure Qdrant collections | Collections from `11-qdrant/01-collections.md` | `infra/docker/qdrant-init.sh` |
| 2.5 Create tickers seed data | THYAO + 10 sample tickers | `scripts/seed_dev_data.py` |
| 2.6 Create n8n workflow scaffold | 01-scheduler through 07-technical | `workflows/*.json` (skeleton) |
| 2.7 Create trading calendar | BIST trading days, holidays | `services/shared/trading_calendar.py` |
| 2.8 Set up schema validation | `jsonschema` validation in Python | `services/shared/validation.py` |

**Files Created:** ~30 new files
**Testing:** `psql` connection test, Redis ping test, Qdrant health check

---

### Week 3: Market Collector (FR-001 to FR-005)
**Goal:** THYAO tick data flows BIST API → PostgreSQL → dashboard in < 2s

| Task | Deliverable | FR |
|------|-------------|-----|
| 3.1 Create BIST API client | `services/market_collector/src/market_collector/client.py` | FR-001 |
| 3.2 Implement tick ingestion | Write ticks to `market_data.ticks` | FR-001 |
| 3.3 Implement OHLCV bar aggregation | 1m, 5m, 15m, 60m bars to `market_data.bars` | FR-002 |
| 3.4 Implement EOD settlement | Daily batch by 18:05 TRT | FR-003 |
| 3.5 Implement BIST-100 index fetch | Index value every 10 sec | FR-004 |
| 3.6 Implement sector indices | All 14 sector indices | FR-005 |
| 3.7 Implement Redis caching | `tick:{ticker}:latest` with 24h TTL | FR-021 |
| 3.8 Emit Redis events | `raw.market.tick`, `raw.market.bar` | FR-001 |
| 3.9 Implement backfill support | Replay with `effective_at` | FR-023 |

**Files Created:** `services/market_collector/` (~15 files)
**Testing:** Unit tests for client, integration test for tick flow

---

### Week 4: KAP Collector (FR-008 to FR-010)
**Goal:** THYAO KAP disclosures classified and alert within 5 min

| Task | Deliverable | FR |
|------|-------------|-----|
| 4.1 Create KAP REST client | `services/kap_collector/src/kap_collector/client.py` | FR-008 |
| 4.2 Implement 5-min polling | Poll KAP API every 5 min | FR-008 |
| 4.3 Implement classification | 14 categories (FR-009) | FR-009 |
| 4.4 Implement material event detection | Earnings, dividend, M&A, board change (FR-010) | FR-010 |
| 4.5 Write to PostgreSQL | `kap.disclosures`, `kap.disclosure_tickers` | FR-020 |
| 4.6 Emit Redis events | `raw.kap.classified` | FR-008 |
| 4.7 Implement retry logic | 3 attempts, exponential backoff | FR-019 |

**Files Created:** `services/kap_collector/` (~12 files)
**Testing:** KAP API mock tests, classification F1 test

---

### Week 5: News Collector (FR-011 to FR-013)
**Goal:** News from 12 Turkish sources ingested every 2 minutes

| Task | Deliverable | FR |
|------|-------------|-----|
| 5.1 Create RSS parser | `services/news_collector/src/news_collector/rss.py` | FR-011 |
| 5.2 Implement 12-source polling | Bloomberg HT, AA, Foreks, Reuters, Bloomberg, CNBC-e, Dünya, Capital, Para, Ekonomim, PwC Türkiye, Bigpara | FR-011 |
| 5.3 Implement content extraction | Scrape article body | FR-011 |
| 5.4 Implement deduplication | Content hash dedup < 3% | FR-012 |
| 5.5 Implement ticker extraction | F1 > 0.85 | FR-013 |
| 5.6 Write to PostgreSQL | `news.articles`, `news.article_tickers` | FR-020 |
| 5.7 Emit Redis events | `raw.news.article` | FR-011 |

**Files Created:** `services/news_collector/` (~12 files)
**Testing:** RSS parse tests, dedup rate test

---

### Week 6: Technical Analysis (FR-024, FR-025)
**Goal:** 40+ technical indicators computed, signal events detected in real-time

| Task | Deliverable | FR |
|------|-------------|-----|
| 6.1 Set up `pandas-ta` | Technical indicator library | FR-024 |
| 6.2 Implement indicator computation | SMA, EMA, RSI, MACD, BB, ATR, OBV, VWAP, ADX, CCI, Stochastic, Williams %R, Ichimoku, Pivot Points, Parabolic SAR, Keltner, MFI, CMF | FR-024 |
| 6.3 Implement bar event handler | Subscribe to `raw.market.bar.close` | FR-024 |
| 6.4 Write to PostgreSQL | `analysis.technical_indicators` | FR-024 |
| 6.5 Implement signal detection | Golden/death cross, RSI >70/<30, MACD crossover, BB breakout, volume spike | FR-025 |
| 6.6 Emit Redis events | `analysis.technical.signal` | FR-025 |
| 6.7 Implement partial data handling | New ticker with < 200 bars | FR-024 |

**Files Created:** `services/technical_analysis/` (~15 files)
**Testing:** Indicator calculation tests, signal detection tests

---

### Week 7: Report Generator + Email System (FR-051, FR-052)
**Goal:** Morning briefing by 08:30 TRT, evening summary by 19:00 TRT

| Task | Deliverable | FR |
|------|-------------|-----|
| 7.1 Create report templates | Jinja2 HTML templates (bilingual) | FR-051, FR-052 |
| 7.2 Implement morning briefing | THYAO technical + news summary | FR-051 |
| 7.3 Implement evening summary | Day's analysis + decisions | FR-052 |
| 7.4 Set up SendGrid/SMTP | `services/notification_dispatch/` | FR-055 |
| 7.5 Implement scheduling | n8n cron at 08:30 and 19:00 | FR-051, FR-052 |
| 7.6 Add disclaimer block | "Bu rapor yatırım tavsiyesi değildir..." | FR-057 |
| 7.7 Implement responsive HTML | Dark-mode aware | FR-056 |

**Files Created:** `services/report_generator/`, `services/notification_dispatch/`, `templates/` (~20 files)
**Testing:** Email render test, deliverability test

---

### Week 8: Dashboard Skeleton + Smoke Tests
**Goal:** Dashboard shows live price + last 5 decisions; all FR-001 to FR-025 tests pass

| Task | Deliverable | FR |
|------|-------------|-----|
| 8.1 Set up Next.js 14 | App Router, TypeScript, Tailwind, shadcn/ui | FR-058 |
| 8.2 Create login page | Email + password, JWT | FR-060 |
| 8.3 Create overview page | Live price for THYAO, BIST-100 index | FR-058 |
| 8.4 Create decisions list | Last 5 decisions with evidence trace | FR-061 |
| 8.5 Implement WebSocket client | Subscribe to `market.update` | FR-059 |
| 8.6 Create system health page | CPU, memory, queue depth | FR-068 |
| 8.7 Create API gateway | FastAPI with auth, rate limiting | FR-022 |
| 8.8 Run smoke tests | End-to-end with THYAO | All FR-001 to FR-025 |
| 8.9 Performance validation | Tick-to-DB < 2s, KAP < 5min | NFR-P01, NFR-P02 |

**Files Created:** `apps/dashboard/`, `apps/api-gateway/` (~40 files)
**Testing:** Playwright e2e tests, k6 load test

---

## Functional Requirements Coverage

| FR Range | Topic | Week |
|----------|-------|------|
| FR-001 to FR-005 | Market data ingestion | Week 3 |
| FR-006 to FR-007 | TEFAS (deferred to Phase 2) | - |
| FR-008 to FR-010 | KAP collector | Week 4 |
| FR-011 to FR-013 | News collector | Week 5 |
| FR-014 to FR-016 | Macro (deferred to Phase 2) | - |
| FR-017 | Historical data | Week 3 |
| FR-018 to FR-019 | Error handling, retry | Week 3-5 |
| FR-020 to FR-021 | PostgreSQL + Redis | Week 2-3 |
| FR-022 | FastAPI endpoints | Week 8 |
| FR-023 | Backfill support | Week 3 |
| FR-024 to FR-025 | Technical analysis | Week 6 |

**Note:** FR-006, FR-007 (TEFAS), FR-014 to FR-016 (Macro) are deferred to Phase 2 per roadmap.

---

## Non-Functional Requirements Validation

| NFR | Target | Validation Method |
|-----|--------|-------------------|
| NFR-P01 (Tick-to-DB) | < 2s | OTel trace |
| NFR-P02 (KAP-to-alert) | < 5 min | KAP-to-alert log |
| NFR-P09 (PostgreSQL read) | < 50ms | pg_stat_statements |
| NFR-P10 (Redis read) | < 5ms | Redis slowlog |
| NFR-A01 (Uptime) | > 99.5% | Uptime monitor |
| NFR-M01 (Coverage) | ≥ 80% | pytest --cov |
| NFR-M03 (Lint) | 0 errors | ruff |

---

## Quality Gates Checklist

Before Week 8 is complete, ALL must pass:

- [ ] Unit test coverage ≥ 80% per service
- [ ] Integration tests 100% pass (testcontainers)
- [ ] Schema validation 100% pass
- [ ] ruff: 0 errors
- [ ] mypy --strict: 0 errors
- [ ] SAST (bandit + trufflehog): 0 high-severity findings
- [ ] THYAO tick data flows end-to-end in < 2s
- [ ] Morning briefing arrives by 08:30 TRT
- [ ] Dashboard shows live price + last 5 decisions

---

## File Structure Created

```
finance-ai-v3/
├── apps/
│   ├── api-gateway/          # Week 8
│   └── dashboard/            # Week 8
├── services/
│   ├── market_collector/    # Week 3
│   ├── kap_collector/       # Week 4
│   ├── news_collector/      # Week 5
│   ├── technical_analysis/   # Week 6
│   ├── report_generator/    # Week 7
│   └── notification_dispatch/ # Week 7
├── workflows/               # Weeks 1-7
├── schemas/                 # Week 1
├── agents/                  # Deferred to Phase 2
├── infra/
│   └── docker/              # Week 1-2
├── tests/                   # Ongoing
└── scripts/                 # Week 1-2
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| BIST API access delayed | Start with public BIST website scrape as fallback |
| KAP API rate limits | Apply for higher quota early; cache aggressively |
| LiteLLM integration complexity | Use OpenAI provider first; add MiniMax in Phase 2 |
| n8n workflow complexity | Use Python scripts called from n8n for complex logic |

---

## Next Steps After Phase 1

**Phase 2 (Weeks 9-16):**
- Scale to all BIST-100 tickers
- Add TEFAS + Macro collectors
- Implement fundamental, news, sentiment, sector agents
- Supervisor agent orchestration
- Decision engine + Risk engine
- Full dashboard with portfolio management

---

## Implementation Mode Transition

This plan is ready for execution. To begin implementation:

1. Review and approve this plan
2. Switch to `code` mode to start Week 1 scaffolding
3. Create feature branches: `feat/W1-scaffolding`, `feat/W2-database`, etc.
4. Follow conventional commits: `feat: FR-001 add BIST tick ingestion`

**Recommended start:** Week 1 scaffolding (Docker Compose, uv, pnpm, Makefile, CI/CD, JSON Schemas)