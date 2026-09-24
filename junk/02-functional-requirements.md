# 02 — Functional Requirements

> **Format:** Each FR has a unique ID, a one-sentence statement, acceptance criteria, related workflows/agents, and a phase tag.
> **Phases:** P1 = MVP (weeks 1–8) · P2 = Production (weeks 9–16) · P3 = Optimization (weeks 17–24)

---

## FR-001 to FR-025 — Market Data Ingestion (P1)

| ID    | Statement                                                                                   | Acceptance Criteria                                                            | Workflows                          | Phase |
|-------|---------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|------------------------------------|-------|
| FR-001| System shall ingest BIST intraday tick data for all equities via the BIST Data Discovery API | Latency < 2s from exchange timestamp to DB write; 100% tick capture             | 02-market-collector                | P1    |
| FR-002| System shall ingest BIST intraday OHLCV bars at 1-min, 5-min, 15-min, 60-min resolutions    | Bar completeness > 99.9% per trading day                                        | 02-market-collector                | P1    |
| FR-003| System shall ingest end-of-day BIST settlement prices within 5 minutes of market close     | Daily batch completes by 18:05 TRT                                              | 02-market-collector                | P1    |
| FR-004| System shall ingest BIST-100 index value every 10 seconds during trading hours             | Gaps < 0.1% of expected samples                                                 | 02-market-collector                | P1    |
| FR-005| System shall ingest BIST sector indices (BIST-FIN, BIST-IND, BIST-SRV, etc.) every minute  | All 14 sector indices present                                                   | 02-market-collector                | P1    |
| FR-006| System shall ingest TEFAS fund NAVs for all public funds (mutual, participation, gold, index, bond) | All 800+ funds ingested by 21:00 TRT                                        | 04-tefas-collector                 | P1    |
| FR-007| System shall ingest TEFAS fund flows (subscriptions/redemptions) daily                     | Daily flow available before next-day pre-market                                 | 04-tefas-collector                 | P1    |
| FR-008| System shall ingest KAP disclosures (all categories) within 5 minutes of publication        | p95 latency < 5 min                                                             | 03-kap-collector                   | P1    |
| FR-009| System shall classify KAP disclosures into the 14 official categories                       | Classification F1 > 0.90                                                        | 03-kap-collector                   | P1    |
| FR-010| System shall detect material KAP events (earnings, dividend, M&A, board change, capital action) | Recall > 0.95 on labeled set                                                 | 03-kap-collector                   | P1    |
| FR-011| System shall ingest news from at least 12 Turkish financial sources every 2 minutes         | All 12 RSS feeds polled; new articles ingested within 2 min                     | 05-news-collector                  | P1    |
| FR-012| System shall deduplicate near-identical news articles within 30 minutes of publication      | Duplicate rate < 3%                                                             | 05-news-collector                  | P1    |
| FR-013| System shall classify news by ticker (BIST), sector, and topic                              | Ticker F1 > 0.85                                                                | 05-news-collector                  | P1    |
| FR-014| System shall ingest TCMB EVDS indicators (policy rate, FX reserves, M2, CPI expectations)   | Daily refresh by 11:00 TRT                                                      | 06-macro-collector                 | P1    |
| FR-015| System shall ingest TÜİK monthly indicators (CPI, PPI, unemployment, GDP) on release day    | Available within 2 hours of TÜİK press release                                  | 06-macro-collector                 | P1    |
| FR-016| System shall ingest BDDK weekly bulletins (sector NPL, capital adequacy, deposits)          | PDF parsed within 24 hours of publication                                       | 06-macro-collector                 | P1    |
| FR-017| System shall maintain 10 years of historical BIST price data                               | Continuous backfill available for any ticker                                    | 02-market-collector                | P1    |
| FR-018| System shall detect and flag data source outages within 60 seconds                          | Alert sent to monitoring channel                                                | 02-market-collector                | P1    |
| FR-019| System shall retry failed ingests with exponential backoff (3 attempts, max 60s)            | Retry log visible in dashboard                                                  | All collectors                     | P1    |
| FR-020| System shall write all raw data to PostgreSQL with full audit (ingested_at, source)         | Audit columns on every row                                                      | All collectors                     | P1    |
| FR-021| System shall cache hot data (latest 30 days) in Redis                                       | p95 read latency < 5ms                                                          | All collectors                     | P1    |
| FR-022| System shall expose all ingested data via FastAPI `/v1/data/*` endpoints                    | OpenAPI spec generated from schemas                                             | 02-market-collector                | P1    |
| FR-023| System shall support replay of historical data with synthetic timestamps                    | Backtest engine can request any date range                                      | 18-backtest-runner                 | P1    |
| FR-024| System shall compute and store 40+ technical indicators (SMA, EMA, RSI, MACD, BB, ATR, etc.)| All indicators materialized in `technical_indicators` table                     | 07-technical-analysis              | P1    |
| FR-025| System shall detect technical signal events (crossover, breakout, divergence) in real time  | Event emitted within 10s of bar close                                           | 07-technical-analysis              | P1    |

## FR-026 to FR-050 — Analysis Layer (P2)

| ID    | Statement                                                                                   | Acceptance Criteria                                                            | Workflows / Agents                  | Phase |
|-------|---------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|-------------------------------------|-------|
| FR-026| System shall run fundamental analysis agent on every quarterly earnings KAP                | Analysis complete within 30 min of KAP publication                             | 08-fundamental-analysis             | P2    |
| FR-027| System shall compute 20+ fundamental ratios (P/E, P/B, ROE, ROA, EV/EBITDA, etc.)          | All ratios materialized for every BIST-100 company                              | 08-fundamental-analysis             | P2    |
| FR-028| System shall run peer comparison for every BIST-100 company against sector peers            | Peer set of 5–10 companies per target                                           | 08-fundamental-analysis             | P2    |
| FR-029| System shall run macro analysis agent on every TCMB/TÜİK release                            | Analysis complete within 15 min of release                                      | 09-macro-analysis                   | P2    |
| FR-030| System shall maintain a macro indicator dashboard (policy rate path, CPI trend, FX reserves)| Dashboard updates within 5 min of new data                                      | 09-macro-analysis                   | P2    |
| FR-031| System shall run news analysis agent on every news article within 2 min of ingestion        | Ticker-relevance + sentiment + materiality scored                               | 10-news-analysis                    | P2    |
| FR-032| System shall run sentiment analysis (Turkish NLP) on every news article                    | Sentiment F1 > 0.80 on labeled set                                              | 11-sentiment-analysis               | P2    |
| FR-033| System shall run sector analysis agent daily at 18:30 TRT                                  | All 14 BIST sectors scored                                                      | 12-sector-analysis                  | P2    |
| FR-034| System shall compute cross-sector correlation matrix weekly                                 | Matrix available every Monday 09:00 TRT                                         | 12-sector-analysis                  | P2    |
| FR-035| System shall embed every news article, KAP disclosure, and analysis result into Qdrant     | Embedding latency < 2s per document                                              | 19-memory-indexer                   | P2    |
| FR-036| System shall retrieve top-K similar historical events for every new signal                 | Recall@10 > 0.85                                                                | 19-memory-indexer                   | P2    |
| FR-037| System shall detect contradictions between evidence streams                                 | Contradiction score on every decision record                                    | 15-decision-engine                  | P2    |
| FR-038| System shall compute novelty score for every signal vs. last 30 days                       | Novelty in [0,1] on every event                                                 | 15-decision-engine                  | P2    |
| FR-039| System shall aggregate evidence from 8 streams into a decision record                      | Every decision has evidence[]                                                   | 15-decision-engine                  | P2    |
| FR-040| System shall apply portfolio-aware filter to every decision (exposure, risk budget)        | Recommendations respect portfolio constraints                                   | 14-portfolio-analysis               | P2    |
| FR-041| System shall compute position sizing based on confidence + risk                            | Kelly-fraction sizing on every rec                                              | 14-portfolio-analysis               | P2    |
| FR-042| System shall run risk assessment agent on every portfolio                                  | Daily risk report (VaR, CVaR, beta)                                             | 13-risk-assessment                  | P2    |
| FR-043| System shall compute 1-day 95% VaR for every portfolio                                     | VaR within 5% of historical-simulation VaR                                      | 13-risk-assessment                  | P2    |
| FR-044| System shall compute concentration risk (HHI) per portfolio                                | HHI recomputed on every holding change                                          | 13-risk-assessment                  | P2    |
| FR-045| System shall detect portfolio drift > 5% from target weights                               | Drift alert within 5 min                                                        | 14-portfolio-analysis               | P2    |
| FR-046| System shall support up to 10 portfolios per user                                          | Isolation enforced                                                              | 14-portfolio-analysis               | P2    |
| FR-047| System shall produce a decision record with full evidence trace for every recommendation   | 100% decisions traceable                                                        | 15-decision-engine                  | P2    |
| FR-048| System shall grade every recommendation: INFO, WARN, CRITICAL, EMERGENCY                   | Grade on every decision record                                                  | 15-decision-engine                  | P2    |
| FR-049| System shall rate-limit alerts: max 5 CRITICAL per ticker per day                          | Limit enforced                                                                  | 17-notification-dispatch            | P2    |
| FR-050| System shall suppress duplicate alerts within 60 min                                       | Dedup hash on every alert                                                       | 17-notification-dispatch            | P2    |

## FR-051 to FR-075 — Output Layer (P2)

| ID    | Statement                                                                                   | Acceptance Criteria                                                            | Workflows                           | Phase |
|-------|---------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|-------------------------------------|-------|
| FR-051| System shall send a morning briefing email by 08:30 TRT every trading day                  | On-time rate > 99%                                                              | 16-report-generation                | P2    |
| FR-052| System shall send an evening summary email by 19:00 TRT every trading day                  | On-time rate > 99%                                                              | 16-report-generation                | P2    |
| FR-053| System shall send a weekly summary email every Friday 19:30 TRT                            | On-time rate > 99%                                                              | 16-report-generation                | P2    |
| FR-054| System shall send a monthly report on the 1st business day of each month                   | On-time rate > 99%                                                              | 16-report-generation                | P2    |
| FR-055| System shall send immediate email + dashboard push for CRITICAL alerts                     | Latency < 30s from decision to email                                            | 17-notification-dispatch            | P2    |
| FR-056| System shall render emails with responsive HTML, dark-mode aware                            | Renders correctly in Gmail, Outlook, Apple Mail                                 | 15-email-system                     | P2    |
| FR-057| System shall include a disclaimer block on every email and recommendation                  | Disclaimer present on 100% of outputs                                           | 15-email-system                     | P2    |
| FR-058| System shall expose a Next.js dashboard with pages: overview, portfolio, alerts, decisions, agents, backtest | All pages render < 1s LCP                                                | 14-dashboard                        | P2    |
| FR-059| System shall push real-time updates via WebSocket to all connected dashboard clients       | Message loss = 0                                                                | 14-dashboard                        | P2    |
| FR-060| System shall support dashboard login via email + password (JWT)                            | JWT 24h refresh                                                                 | 14-dashboard                        | P2    |
| FR-061| System shall expose a decision detail view with full evidence trace                        | Every evidence item clickable to source                                         | 14-dashboard                        | P2    |
| FR-062| System shall expose an agent activity view (last 24h, last 7d)                             | Activity log queryable                                                          | 14-dashboard                        | P2    |
| FR-063| System shall expose a backtest view (run new, view historical)                             | Backtest submission + result rendering                                          | 14-dashboard                        | P2    |
| FR-064| System shall expose an alert inbox with mark-as-read                                         | Read state persisted                                                            | 14-dashboard                        | P2    |
| FR-065| System shall expose a portfolio editor (add/remove holdings, set target weights)           | Edits validated                                                                 | 14-dashboard                        | P2    |
| FR-066| System shall expose a settings page (notification prefs, source toggles)                   | Settings persisted                                                              | 14-dashboard                        | P2    |
| FR-067| System shall expose an API key management page (read-only, read-write)                     | Keys hashed at rest                                                             | 14-dashboard                        | P2    |
| FR-068| System shall expose a system health page (CPU, memory, queue depth, LLM cost)              | Updated every 30s                                                               | 14-dashboard                        | P2    |
| FR-069| System shall render all prices in TRY by default with USD toggle                           | Toggle persists per user                                                        | 14-dashboard                        | P2    |
| FR-070| System shall render all timestamps in Europe/Istanbul                                      | No UTC displayed to user                                                        | 14-dashboard                        | P2    |

## FR-071 to FR-090 — Memory & Backtest (P3)

| ID    | Statement                                                                                   | Acceptance Criteria                                                            | Workflows                           | Phase |
|-------|---------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|-------------------------------------|-------|
| FR-071| System shall retain 2 years of decision records with full evidence trace                   | Retention enforced                                                              | 13-decision-engine                  | P3    |
| FR-072| System shall run weekly backtest on past recommendations vs. realized outcomes             | Backtest report every Monday 06:00 TRT                                          | 18-backtest-runner                  | P3    |
| FR-073| System shall compute hit-rate metric: % of ≥0.8-confidence recommendations that played out | Hit rate displayed on dashboard                                                 | 18-backtest-runner                  | P3    |
| FR-074| System shall recompute decision weights monthly based on backtest results                  | Weights versioned, rollback supported                                           | 13-decision-engine                  | P3    |
| FR-075| System shall detect "regime change" (bull→bear, range→trend) and alert                     | Regime detector runs daily                                                      | 09-macro-analysis                   | P3    |
| FR-076| System shall store embeddings with 2-year retention                                         | Qdrant retention policy enforced                                                | 11-qdrant                           | P3    |
| FR-077| System shall support similarity search across historical decisions                         | Recall@10 > 0.85                                                                | 11-qdrant                           | P3    |
| FR-078| System shall support "what-if" simulation: replay a past decision under different weights  | Simulation completes < 60s                                                      | 18-backtest-runner                  | P3    |
| FR-079| System shall detect "decision drift": gradual change in agent outputs over time            | Drift report weekly                                                             | 18-backtest-runner                  | P3    |
| FR-080| System shall support A/B testing of prompt versions                                         | 50/50 traffic split                                                             | 08-prompts                          | P3    |
| FR-081| System shall support per-agent cost tracking                                                | Cost dashboard per agent                                                        | 16-monitoring                       | P3    |
| FR-082| System shall support LLM model swap (e.g. GPT-5 → Claude) via config                        | No code changes                                                                 | 04-system-architecture              | P3    |
| FR-083| System shall retry failed LLM calls on a different provider (circuit breaker pattern)      | Failover < 5s                                                                   | 04-system-architecture              | P3    |
| FR-084| System shall log every LLM call with prompt, completion, tokens, cost, latency             | 100% calls logged                                                               | 16-monitoring                       | P3    |
| FR-085| System shall support prompt regression testing                                             | Promptfoo suite runs on every PR                                                | 17-testing                          | P3    |
| FR-086| System shall support data quality tests                                                    | Great Expectations suite runs daily                                             | 17-testing                          | P3    |
| FR-087| System shall support load tests on critical endpoints                                      | k6 suite runs weekly                                                            | 17-testing                          | P3    |
| FR-088| System shall support chaos engineering (kill random containers)                            | Monthly exercise                                                                | 17-testing                          | P3    |
| FR-089| System shall detect anomalies in agent outputs (outlier detection)                         | Anomaly flag on agent output                                                    | 16-monitoring                       | P3    |
| FR-090| System shall expose a Slack webhook for critical alerts                                    | Slack message within 30s                                                        | 17-notification-dispatch            | P3    |

## FR-091 to FR-105 — Compliance, Security, Ops (P3)

| ID    | Statement                                                                                   | Acceptance Criteria                                                            | Workflows                           | Phase |
|-------|---------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|-------------------------------------|-------|
| FR-091| System shall run compliance check on every recommendation before delivery                  | 100% recommendations checked                                                   | 20-compliance-check                 | P3    |
| FR-092| System shall block recommendations that violate compliance rules                            | Blocked recs logged with reason                                                 | 20-compliance-check                 | P3    |
| FR-093| System shall include "not investment advice" disclaimer on every output                    | 100% outputs                                                                    | All outputs                         | P3    |
| FR-094| System shall redact PII from logs                                                           | PII scan on log ingest                                                          | 16-monitoring                       | P3    |
| FR-095| System shall encrypt all data at rest (AES-256)                                            | Disk encryption verified                                                        | 10-database                         | P3    |
| FR-096| System shall encrypt all data in transit (TLS 1.3)                                         | TLS scan passes                                                                 | All                                 | P3    |
| FR-097| System shall rotate API keys every 90 days                                                 | Rotation script + alert                                                         | 18-coding-standards                 | P3    |
| FR-098| System shall audit every dashboard login                                                   | Audit log immutable                                                             | 14-dashboard                        | P3    |
| FR-099| System shall audit every API call                                                          | Audit log queryable                                                             | 04-system-architecture              | P3    |
| FR-100| System shall support role-based access control (RBAC): viewer, analyst, admin              | Roles enforced on every endpoint                                                | 14-dashboard                        | P3    |
| FR-101| System shall run daily backup of PostgreSQL (full + WAL)                                    | Backup verified by restore test                                                 | 10-database                         | P3    |
| FR-102| System shall restore from backup within 1 hour                                             | DR exercise quarterly                                                           | 10-database                         | P3    |
| FR-103| System shall support blue/green deployment                                                 | Zero-downtime deploy                                                            | 18-coding-standards                 | P3    |
| FR-104| System shall support canary deployment for new agent prompts                               | 5% canary → 100%                                                                | 18-coding-standards                 | P3    |
| FR-105| System shall expose a /health endpoint returning component status                          | Status aggregated from all services                                             | 16-monitoring                       | P3    |

---

## Summary by Phase

| Phase | FR count | Theme                                                            |
|-------|----------|------------------------------------------------------------------|
| P1    | 25       | Market data ingestion + basic technical analysis                |
| P2    | 45       | Multi-agent analysis + decision engine + outputs                |
| P3    | 35       | Memory, backtest, compliance, security, ops                     |
| Total | 105      |                                                                  |

Every FR MUST link to at least one workflow file in `06-workflows/` and at least one test case in `17-testing/`.
