# 06 — Workflows Overview

> 21 files (this overview + 20 workflow specs). Every workflow runs in n8n, with Python step implementations under `workflows/steps/`.

## Workflow Catalog

| #  | Workflow                  | Trigger                 | Owner Agent       | Phase |
|----|---------------------------|-------------------------|-------------------|-------|
| 01 | scheduler                 | cron                    | (infra)           | P1    |
| 02 | market_collector          | schedule + event        | —                 | P1    |
| 03 | kap_collector             | schedule (5 min)        | Fundamental       | P1    |
| 04 | tefas_collector            | schedule (EOD)          | —                 | P1    |
| 05 | news_collector            | schedule (2 min)        | News              | P1    |
| 06 | macro_collector           | schedule (daily)        | Macro             | P1    |
| 07 | technical_analysis        | event                   | Technical         | P1    |
| 08 | fundamental_analysis      | event (KAP material)    | Fundamental       | P2    |
| 09 | macro_analysis            | event (TCMB/TÜİK)       | Macro             | P2    |
| 10 | news_analysis             | event (new article)     | News              | P2    |
| 11 | sentiment_analysis        | event (after news)      | Sentiment         | P2    |
| 12 | sector_analysis           | schedule (daily 18:30)  | Sector            | P2    |
| 13 | risk_assessment           | schedule (daily) + event| Risk              | P2    |
| 14 | portfolio_analysis        | event                   | Portfolio         | P2    |
| 15 | decision_engine           | event                   | Supervisor        | P2    |
| 16 | report_generation         | schedule + event        | Report            | P2    |
| 17 | notification_dispatch     | event                   | —                 | P2    |
| 18 | backtest_runner           | schedule (weekly Mon)   | Backtest          | P3    |
| 19 | memory_indexer            | event (after analysis)  | Memory            | P2    |
| 20 | compliance_check          | event (before delivery) | Compliance        | P3    |

## Common Workflow Anatomy

Every workflow file MUST define:
1. **Purpose** — one sentence
2. **Trigger** — schedule | event | webhook | manual
3. **Input schema** — reference to `09-json-schemas/`
4. **Output schema** — reference to `09-json-schemas/`
5. **Steps** — ordered list with retry/timeout
6. **Error handling** — failure mode table
7. **n8n nodes** — concrete configuration
8. **Test cases** — minimum 3 (happy / edge / failure)
9. **Idempotency key** — format
10. **SLA** — p50 / p95 latency target
