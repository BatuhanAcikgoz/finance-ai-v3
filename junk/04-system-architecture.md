# 04 — System Architecture

> **Style:** Event-driven, microservices-ish, container-first.
> **Stack:** n8n + Docker + Redis + PostgreSQL + Qdrant + LiteLLM + FastAPI + Next.js

---

## 1. High-Level Topology

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL DATA SOURCES                              │
│   BIST API  │  TEFAS  │  KAP  │  News RSS  │  TCMB EVDS  │  TÜİK  │  BDDK         │
└─────────┬──────────┬────────┬────────┬──────────┬────────────┬────────┬──────────┘
          │          │        │        │          │            │        │
          ▼          ▼        ▼        ▼          ▼            ▼        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION LAYER  (FastAPI + n8n)                          │
│   market_collector │ tefas_collector │ kap_collector │ news_collector │ macro    │
└─────────┬───────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          EVENT BUS  (Redis pub/sub + streams)                     │
│   channels: raw.market.* │ raw.kap.* │ raw.news.* │ raw.macro.* │ evt.decision.*  │
└─────────┬───────────────────────────────────────────────────────────────────────┘
          │
   ┌──────┴────────┬─────────────┬──────────────┬───────────────┬───────────────┐
   ▼               ▼             ▼              ▼               ▼               ▼
┌─────────┐ ┌────────────┐ ┌──────────┐ ┌────────────┐ ┌─────────────┐ ┌──────────┐
│Technical│ │Fundamental │ │  News    │ │ Sentiment  │ │   Macro     │ │  Sector  │
│ Analysis│ │  Analysis  │ │ Analysis │ │  Analysis  │ │  Analysis   │ │ Analysis │
└────┬────┘ └─────┬──────┘ └────┬─────┘ └─────┬──────┘ └──────┬──────┘ └────┬─────┘
     │            │             │             │               │             │
     └────────────┴─────────────┴─────────────┴───────────────┴─────────────┘
                                       │
                                       ▼
                          ┌────────────────────────┐
                          │   Supervisor Agent     │
                          │  (evidence aggregation)│
                          └───────────┬────────────┘
                                      │
                  ┌───────────────────┼───────────────────┐
                  ▼                   ▼                   ▼
          ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
          │ Risk Engine  │   │  Portfolio   │   │  Decision    │
          │              │   │   Engine     │   │   Engine     │
          └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
                 │                  │                  │
                 └──────────────────┴──────────────────┘
                                    │
                                    ▼
                          ┌────────────────────────┐
                          │   Compliance Agent     │
                          └───────────┬────────────┘
                                      │
                          ┌───────────┴────────────┐
                          ▼                        ▼
                  ┌──────────────┐         ┌──────────────┐
                  │   Report     │         │ Notification │
                  │  Generator   │         │   Dispatch   │
                  └──────┬───────┘         └──────┬───────┘
                         │                        │
                         ▼                        ▼
                  ┌──────────────┐         ┌──────────────┐
                  │   Email +    │         │  Dashboard   │
                  │  Dashboard   │         │  WebSocket   │
                  └──────────────┘         └──────────────┘
```

## 2. Component Catalog

| Component             | Technology           | Responsibility                                                      | Scales by        |
|-----------------------|----------------------|---------------------------------------------------------------------|------------------|
| market_collector      | FastAPI + aiohttp    | BIST tick/bar ingestion                                             | Horizontal       |
| tefas_collector       | FastAPI + BeautifulSoup | TEFAS HTML scrape + parse                                         | Single instance  |
| kap_collector         | FastAPI + httpx      | KAP REST polling + classification                                   | Single instance  |
| news_collector        | FastAPI + feedparser | RSS + scrape                                                        | Horizontal       |
| macro_collector       | FastAPI + httpx      | TCMB + TÜİK + BDDK                                                  | Single instance  |
| event_bus             | Redis 7 ( Streams)   | Pub/sub + stream + DLQ                                              | Cluster (3-node) |
| postgres              | PostgreSQL 16        | Source of truth for all structured data                              | Primary + 2 reps |
| qdrant                | Qdrant 1.10          | Vector store for embeddings                                          | Horizontal       |
| llm_router            | LiteLLM 1.x          | Provider-agnostic LLM access, fallback, cost tracking               | Single instance  |
| supervisor_agent      | FastAPI + LiteLLM    | Top-level orchestrator                                              | Horizontal       |
| specialist_agents     | FastAPI + LiteLLM    | Technical, fundamental, macro, news, sentiment, sector, risk, etc.  | Horizontal       |
| decision_engine       | FastAPI              | Evidence aggregation, confidence scoring                            | Horizontal       |
| risk_engine           | FastAPI + numpy/pandas | VaR, CVaR, correlation                                             | Horizontal       |
| report_generator      | FastAPI + Jinja2     | Email + dashboard report rendering                                  | Horizontal       |
| notification_dispatch | FastAPI + SendGrid   | Email + Slack + dashboard push                                      | Horizontal       |
| dashboard             | Next.js 14           | User-facing UI                                                      | Stateless        |
| api_gateway           | FastAPI + nginx      | Single entry point, auth, rate limit                                | Active-active    |
| n8n                   | n8n 1.x              | Workflow orchestration (cron + webhook)                             | Single instance  |
| monitoring            | Prometheus + Grafana | Metrics + dashboards                                                | Single instance  |
| logging               | Loki + Promtail      | Structured log aggregation                                           | Single instance  |
| tracing               | Jaeger + OTel Collector | Distributed traces                                                | Single instance  |

## 3. Data Flow (Canonical Patterns)

### 3.1 Real-time tick flow
```
BIST API → market_collector (FastAPI)
         → Redis stream "raw.market.bist.tick"
         → technical_analysis workflow (consumes)
         → PostgreSQL "ticks" table (append)
         → Redis cache "tick:{ticker}" (latest)
         → WebSocket broadcast to dashboard
```

### 3.2 KAP disclosure flow
```
KAP REST → kap_collector (polls every 5 min)
        → classify with LLM (LiteLLM)
        → Redis stream "raw.kap.classified"
        → embed in Qdrant (kap_embeddings collection)
        → PostgreSQL "kap_disclosures" table
        → fundamental_analysis workflow (if material)
        → supervisor agent (if affects portfolio)
        → decision_engine → compliance → notification
```

### 3.3 Decision flow
```
[event] → supervisor_agent
       → fan-out to: technical, fundamental, macro, news, sentiment, sector
       → each returns {signal, strength, confidence}
       → supervisor aggregates → decision_engine
       → risk_engine + portfolio_engine enrich
       → compliance_agent reviews
       → report_generator + notification_dispatch
       → PostgreSQL "decisions" table (with evidence[])
       → WebSocket push to dashboard
```

### 3.4 Backtest flow
```
[cron: every Monday 06:00 TRT]
   → backtest_runner workflow
   → reads past decisions from PostgreSQL (last 4 weeks)
   → reads realized outcomes from price history
   → computes hit-rate, calibration, attribution
   → writes report to PostgreSQL "backtests" table
   → recalibrates decision weights (opt-in, requires approval)
```

## 4. Container Topology

```yaml
# docker-compose.yml (simplified)
services:
  # === Ingestion ===
  market-collector:    { image: finance-ai-v3/market-collector:latest, replicas: 2 }
  tefas-collector:     { image: finance-ai-v3/tefas-collector:latest, replicas: 1 }
  kap-collector:       { image: finance-ai-v3/kap-collector:latest, replicas: 1 }
  news-collector:      { image: finance-ai-v3/news-collector:latest, replicas: 2 }
  macro-collector:     { image: finance-ai-v3/macro-collector:latest, replicas: 1 }

  # === Agents ===
  supervisor:          { image: finance-ai-v3/supervisor:latest, replicas: 2 }
  technical-agent:     { image: finance-ai-v3/agents:latest, replicas: 2 }
  fundamental-agent:   { image: finance-ai-v3/agents:latest, replicas: 2 }
  macro-agent:         { image: finance-ai-v3/agents:latest, replicas: 1 }
  news-agent:          { image: finance-ai-v3/agents:latest, replicas: 2 }
  sentiment-agent:     { image: finance-ai-v3/agents:latest, replicas: 2 }
  sector-agent:        { image: finance-ai-v3/agents:latest, replicas: 1 }
  risk-agent:          { image: finance-ai-v3/agents:latest, replicas: 1 }
  portfolio-agent:     { image: finance-ai-v3/agents:latest, replicas: 1 }
  backtest-agent:      { image: finance-ai-v3/agents:latest, replicas: 1 }
  compliance-agent:    { image: finance-ai-v3/agents:latest, replicas: 1 }
  memory-agent:        { image: finance-ai-v3/agents:latest, replicas: 1 }
  report-agent:        { image: finance-ai-v3/agents:latest, replicas: 1 }

  # === Engines ===
  decision-engine:     { image: finance-ai-v3/decision-engine:latest, replicas: 2 }
  risk-engine:         { image: finance-ai-v3/risk-engine:latest, replicas: 1 }
  report-generator:    { image: finance-ai-v3/report-generator:latest, replicas: 1 }
  notification-dispatch: { image: finance-ai-v3/notification-dispatch:latest, replicas: 1 }

  # === API + UI ===
  api-gateway:         { image: finance-ai-v3/api-gateway:latest, replicas: 2 }
  dashboard:           { image: finance-ai-v3/dashboard:latest, replicas: 2 }

  # === Infra ===
  postgres:            { image: postgres:16, replicas: 1, volumes: [pg-data] }
  redis:               { image: redis:7, replicas: 3, command: ["redis-server", "--cluster-enabled", "yes"] }
  qdrant:              { image: qdrant/qdrant:v1.10.1, replicas: 1, volumes: [qdrant-data] }
  n8n:                 { image: n8nio/n8n:latest, replicas: 1 }
  litellm:             { image: ghcr.io/berriai/litellm:main, replicas: 1 }

  # === Observability ===
  prometheus:          { image: prom/prometheus:latest }
  grafana:             { image: grafana/grafana:latest }
  loki:                { image: grafana/loki:latest }
  promtail:            { image: grafana/promtail:latest }
  jaeger:              { image: jaegertracing/all-in-one:latest }
  otel-collector:      { image: otel/opentelemetry-collector:latest }
```

## 5. Network & Security

- **Single entry point:** All external traffic through `api-gateway` (nginx + FastAPI).
- **mTLS** between services (cert-manager in k8s, self-signed certs in Docker Compose).
- **No service exposes a port externally** except `api-gateway` (443) and `dashboard` (443).
- **Secrets:** Vault (production) / `.env` (dev) — never in image.
- **Rate limits:** 100 req/min per IP on `/v1/*`; 10 req/min on `/v1/auth/*`.

## 6. Failure Modes & Mitigations

| Failure                          | Mitigation                                                                  |
|----------------------------------|-----------------------------------------------------------------------------|
| BIST API down                    | Switch to websocket; if also down, alert + use cached data ≤ 5 min          |
| KAP API down                     | Retry every 5 min; alert after 15 min                                       |
| News RSS down                    | Skip feed, log, retry in 30 min                                             |
| PostgreSQL primary down          | Promote replica; alert; DLQ drained after recovery                          |
| Redis cluster down               | Fallback to direct PostgreSQL reads; alert                                  |
| Qdrant down                      | Skip similarity search; downgrade confidence; alert                         |
| LiteLLM down                     | All LLM calls fail-fast; agents return INSUFFICIENT_EVIDENCE                |
| MiniMax provider rate-limited    | Failover to GPT-5 via LiteLLM; log cost difference                          |
| n8n down                         | Cron jobs skipped; manual trigger after recovery                            |
| Dashboard down                   | Emails still sent; users notified                                           |
| Email provider down              | Retry 3×; then queue + alert; user can read on dashboard                    |

## 7. Capacity Planning (Initial)

| Resource         | Initial allocation | Growth ceiling |
|------------------|--------------------|----------------|
| CPU (total)      | 32 vCPU            | 128 vCPU       |
| Memory (total)   | 64 GB              | 256 GB         |
| PostgreSQL disk  | 200 GB SSD         | 1 TB SSD       |
| Qdrant disk      | 50 GB SSD          | 500 GB SSD     |
| Redis memory     | 8 GB               | 32 GB          |
| Network egress   | 100 GB/month       | 1 TB/month     |

## 8. Deployment Topology

- **Dev:** Single Docker Compose on a developer laptop (16 GB RAM).
- **Staging:** Single-node Docker Compose on a 16-vCPU / 32-GB VM.
- **Production:** Kubernetes cluster (3 worker nodes, 16 vCPU / 32 GB each).

## 9. Technology Decisions (Rationale)

| Decision                          | Choice                | Why                                                                     |
|-----------------------------------|-----------------------|-------------------------------------------------------------------------|
| Workflow orchestration            | n8n                   | Visual, debuggable, cron-native, self-hostable                          |
| Container runtime                 | Docker + Compose / k8s| Standard, portable                                                      |
| Relational DB                     | PostgreSQL 16         | Mature, JSONB, partitioning, logical replication                        |
| Cache + message bus               | Redis 7               | Streams + pub/sub in one product                                        |
| Vector DB                         | Qdrant                | Fast, Rust, payload filtering, good Python SDK                          |
| LLM gateway                       | LiteLLM               | Provider-agnostic, cost tracking, fallback, OpenAI-compatible API       |
| Service framework                 | FastAPI               | Async, type-safe, OpenAPI auto-generated                                |
| Dashboard framework               | Next.js 14 (App Router)| RSC, streaming, TypeScript                                              |
| Observability                     | Prometheus + Loki + Jaeger | Open-source standard, integrates with everything                  |
| Programming language              | Python 3.12           | Best AI/finance library ecosystem                                       |
