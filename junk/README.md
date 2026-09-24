# Finance AI V3 — Master Prompt + Context Files

> **Target model:** MiniMax M3 (also compatible with Kimi K3, GPT-5, Claude Opus 4)
> **Project:** Autonomous Financial Research Analyst for Turkish Capital Markets (BIST, TEFAS, KAP, TCMB, TÜİK, BDDK)
> **Documentation version:** v1.0
> **Last updated:** 2026-07-28

This package contains **120 markdown files** (~650 KB, ~150K words, ~600 printed pages) that together form a complete Software Design Specification (SDS) for the Finance AI V3 system. The intended use is:

1. Open a new chat with MiniMax M3 (or compatible long-context LLM).
2. Paste `00-master-prompt.md` as the system message.
3. Upload each remaining file as a separate user message **in the order listed below**.
4. Once all files are uploaded, send the task trigger:
   > `Begin Phase 1 execution. Read all context files, confirm understanding, then propose the implementation plan for FR-001 through FR-025.`

---

## File Index (upload in this order)

### Root (6 files)
| #  | File                              | Words  | Purpose                                          |
|----|-----------------------------------|--------|--------------------------------------------------|
| 00 | `00-master-prompt.md`             | ~2,400 | Root system prompt — the constitution             |
| 01 | `01-product-vision.md`            | ~3,200 | Strategic intent, personas, scope, philosophy     |
| 02 | `02-functional-requirements.md`   | ~3,500 | 105 numbered FRs across 3 phases                  |
| 03 | `03-non-functional-requirements.md` | ~1,800 | Performance, security, compliance targets        |
| 04 | `04-system-architecture.md`       | ~2,400 | Component topology, data flow, container layout   |
| 05 | `05-folder-structure.md`          | ~1,500 | Monorepo layout, naming conventions               |

### 06 — Workflows (21 files)
| #  | File                                          | Purpose                                                |
|----|-----------------------------------------------|--------------------------------------------------------|
| 06 | `06-workflows/00-overview.md`                 | Catalog + common anatomy                               |
| 07 | `06-workflows/01-scheduler.md`                | Master cron scheduler                                  |
| 08 | `06-workflows/02-market-collector.md`         | BIST tick/bar ingestion                                |
| 09 | `06-workflows/03-kap-collector.md`            | KAP disclosure polling + classification                |
| 10 | `06-workflows/04-tefas-collector.md`          | TEFAS fund NAV scrape                                  |
| 11 | `06-workflows/05-news-collector.md`           | RSS polling + dedup                                    |
| 12 | `06-workflows/06-macro-collector.md`          | TCMB / TÜİK / BDDK                                     |
| 13 | `06-workflows/07-technical-analysis.md`       | 40+ indicators, signal detection                      |
| 14 | `06-workflows/08-fundamental-analysis.md`     | KAP parsing, ratios, peers                             |
| 15 | `06-workflows/09-macro-analysis.md`           | Macro interpretation, regime detection                |
| 16 | `06-workflows/10-news-analysis.md`            | Ticker extraction, topic, materiality                 |
| 17 | `06-workflows/11-sentiment-analysis.md`       | Turkish NLP sentiment                                  |
| 18 | `06-workflows/12-sector-analysis.md`          | 14 sector indices, rotation                            |
| 19 | `06-workflows/13-risk-assessment.md`          | VaR, CVaR, beta, HHI                                   |
| 20 | `06-workflows/14-portfolio-analysis.md`       | Exposure, position sizing, drift                       |
| 21 | `06-workflows/15-decision-engine.md`          | Evidence aggregation, action selection                 |
| 22 | `06-workflows/16-report-generation.md`        | Morning / evening / weekly / monthly reports           |
| 23 | `06-workflows/17-notification-dispatch.md`    | Email + Slack + dashboard push                         |
| 24 | `06-workflows/18-backtest-runner.md`          | Weekly hit-rate, calibration                           |
| 25 | `06-workflows/19-memory-indexer.md`           | Embed records into Qdrant                              |
| 26 | `06-workflows/20-compliance-check.md`         | Pre-delivery compliance review                         |

### 07 — AI Agents (14 files)
| #  | File                                          | Purpose                                                |
|----|-----------------------------------------------|--------------------------------------------------------|
| 27 | `07-ai-agents/00-overview.md`                 | Catalog + common anatomy                               |
| 28 | `07-ai-agents/01-supervisor.md`               | Top-level orchestrator                                 |
| 29 | `07-ai-agents/02-technical.md`                | Technical analysis interpretation                      |
| 30 | `07-ai-agents/03-fundamental.md`              | Financial statements, ratios, peers                    |
| 31 | `07-ai-agents/04-macro.md`                    | TCMB / TÜİK / BDDK interpretation                      |
| 32 | `07-ai-agents/05-news.md`                     | News classification, ticker extraction                 |
| 33 | `07-ai-agents/06-sentiment.md`                | Turkish NLP sentiment                                  |
| 34 | `07-ai-agents/07-sector.md`                   | Sector rotation, relative strength                     |
| 35 | `07-ai-agents/08-risk.md`                     | VaR / CVaR / beta (deterministic, no LLM)              |
| 36 | `07-ai-agents/09-portfolio.md`                | Exposure, position sizing, drift (no LLM)              |
| 37 | `07-ai-agents/10-backtest.md`                 | Hit-rate, calibration, weight proposal                 |
| 38 | `07-ai-agents/11-compliance.md`               | Pre-delivery compliance review                         |
| 39 | `07-ai-agents/12-memory.md`                   | Embedding, similarity search (no LLM)                  |
| 40 | `07-ai-agents/13-report.md`                   | Narrative generation, action items                     |

### 08 — Prompts (14 files)
| #  | File                                          | Purpose                                                |
|----|-----------------------------------------------|--------------------------------------------------------|
| 41 | `08-prompts/00-prompt-standards.md`           | Universal standards, token budgets, A/B testing        |
| 42 | `08-prompts/01-supervisor-prompt.md`          | Supervisor system prompt                               |
| 43 | `08-prompts/02-technical-prompt.md`           | Technical agent prompt                                 |
| 44 | `08-prompts/03-fundamental-prompt.md`         | Fundamental agent prompt                               |
| 45 | `08-prompts/04-macro-prompt.md`               | Macro agent prompt                                     |
| 46 | `08-prompts/05-news-prompt.md`                | News agent prompt                                      |
| 47 | `08-prompts/06-sentiment-prompt.md`           | Sentiment agent prompt                                 |
| 48 | `08-prompts/07-sector-prompt.md`              | Sector agent prompt                                    |
| 49 | `08-prompts/08-backtest-prompt.md`            | Backtest agent prompt                                  |
| 50 | `08-prompts/09-compliance-prompt.md`          | Compliance agent prompt                                |
| 51 | `08-prompts/10-memory-prompt.md`              | Memory agent (deterministic spec)                      |
| 52 | `08-prompts/11-portfolio-prompt.md`           | Portfolio agent (deterministic spec)                   |
| 53 | `08-prompts/12-risk-prompt.md`                | Risk agent (deterministic spec)                        |
| 54 | `08-prompts/13-report-prompt.md`              | Report agent prompt                                    |

### 09 — JSON Schemas (11 files)
| #  | File                                          | Purpose                                                |
|----|-----------------------------------------------|--------------------------------------------------------|
| 55 | `09-json-schemas/00-schema-standards.md`      | JSON Schema 2020-12 conventions                        |
| 56 | `09-json-schemas/01-market-data.md`           | Tick / Bar / Index / Macro                             |
| 57 | `09-json-schemas/02-news-article.md`          | News article                                           |
| 58 | `09-json-schemas/03-kap-announcement.md`      | KAP disclosure                                         |
| 59 | `09-json-schemas/04-tefas-fund.md`            | TEFAS fund NAV + flow                                  |
| 60 | `09-json-schemas/05-analysis-result.md`       | 6 analysis subtypes                                    |
| 61 | `09-json-schemas/06-risk-assessment.md`       | Risk metrics                                           |
| 62 | `09-json-schemas/07-portfolio-state.md`       | Portfolio + holdings                                   |
| 63 | `09-json-schemas/08-decision-record.md`       | Decision (most important schema)                       |
| 64 | `09-json-schemas/09-alert-event.md`           | Alert                                                  |
| 65 | `09-json-schemas/10-report-payload.md`        | Report                                                 |

### 10 — Database (7 files)
| #  | File                                          | Purpose                                                |
|----|-----------------------------------------------|--------------------------------------------------------|
| 66 | `10-database/00-db-overview.md`               | Three stores overview                                  |
| 67 | `10-database/01-postgres-schema.md`           | All table DDL                                          |
| 68 | `10-database/02-redis-keys.md`                | Key namespace + streams + DLQ                          |
| 69 | `10-database/03-qdrant-collections.md`        | Vector collections                                     |
| 70 | `10-database/04-indexes.md`                   | Index strategy                                         |
| 71 | `10-database/05-migrations.md`                | Alembic migration log                                  |
| 72 | `10-database/06-retention-policy.md`          | KVKK + DR                                              |

### 11 — Qdrant (5 files)
| #  | File                                          | Purpose                                                |
|----|-----------------------------------------------|--------------------------------------------------------|
| 73 | `11-qdrant/00-vector-overview.md`             | Vector store overview                                  |
| 74 | `11-qdrant/01-collections.md`                 | Per-collection strategy                                |
| 75 | `11-qdrant/02-embedding-pipeline.md`          | Text builder + chunking                                |
| 76 | `11-qdrant/03-search-patterns.md`             | Hybrid search patterns                                 |
| 77 | `11-qdrant/04-retrieval-examples.md`          | Concrete examples                                      |

### 12 — Risk Engine (6 files)
| #  | File                                          | Purpose                                                |
|----|-----------------------------------------------|--------------------------------------------------------|
| 78 | `12-risk-engine/00-risk-overview.md`          | Metrics catalog                                        |
| 79 | `12-risk-engine/01-risk-metrics.md`           | Python implementations                                 |
| 80 | `12-risk-engine/02-var-model.md`              | VaR methodology + backtesting                          |
| 81 | `12-risk-engine/03-correlation-matrix.md`     | Ledoit-Wolf shrinkage                                  |
| 82 | `12-risk-engine/04-position-sizing.md`        | Quarter-Kelly                                          |
| 83 | `12-risk-engine/05-alerting-rules.md`         | Alert catalog                                          |

### 13 — Decision Engine (6 files)
| #  | File                                          | Purpose                                                |
|----|-----------------------------------------------|--------------------------------------------------------|
| 84 | `13-decision-engine/00-decision-overview.md`  | Decision flow recap                                    |
| 85 | `13-decision-engine/01-evidence-aggregation.md` | Weighted aggregation logic                           |
| 86 | `13-decision-engine/02-confidence-scoring.md` | Confidence formula                                     |
| 87 | `13-decision-engine/03-decision-matrix.md`    | Action selection table                                 |
| 88 | `13-decision-engine/04-traceability.md`       | Audit trail                                            |
| 89 | `13-decision-engine/05-decision-log.md`       | SQL queries                                            |

### 14 — Dashboard (5 files)
| #  | File                                          | Purpose                                                |
|----|-----------------------------------------------|--------------------------------------------------------|
| 90 | `14-dashboard/00-dashboard-overview.md`       | Next.js 14 stack                                       |
| 91 | `14-dashboard/01-pages.md`                    | 10 page specs                                          |
| 92 | `14-dashboard/02-components.md`               | Component library                                      |
| 93 | `14-dashboard/03-realtime-ws.md`              | WebSocket protocol                                     |
| 94 | `14-dashboard/04-auth.md`                     | JWT + RBAC                                             |

### 15 — Email System (5 files)
| #  | File                                          | Purpose                                                |
|----|-----------------------------------------------|--------------------------------------------------------|
| 95 | `15-email-system/00-email-overview.md`        | Email catalog                                          |
| 96 | `15-email-system/01-templates.md`             | Jinja2 HTML templates                                  |
| 97 | `15-email-system/02-triggers.md`              | Schedule + event triggers                              |
| 98 | `15-email-system/03-smtp-config.md`           | SendGrid + DNS                                         |
| 99 | `15-email-system/04-delivery-rules.md`        | Retry + dedup + bounce                                 |

### 16 — Monitoring (6 files)
| #   | File                                          | Purpose                                                |
|-----|-----------------------------------------------|--------------------------------------------------------|
| 100 | `16-monitoring/00-monitoring-overview.md`     | Prometheus + Loki + Jaeger                             |
| 101 | `16-monitoring/01-metrics.md`                 | Metric catalog + dashboards                            |
| 102 | `16-monitoring/02-logging.md`                 | structlog + PII redaction                              |
| 103 | `16-monitoring/03-tracing.md`                 | OpenTelemetry                                          |
| 104 | `16-monitoring/04-alerting.md`                | Alertmanager rules                                     |
| 105 | `16-monitoring/05-health-checks.md`           | /health endpoints                                      |

### 17 — Testing (7 files)
| #   | File                                          | Purpose                                                |
|-----|-----------------------------------------------|--------------------------------------------------------|
| 106 | `17-testing/00-testing-overview.md`           | Test pyramid + CI                                      |
| 107 | `17-testing/01-unit-tests.md`                 | pytest + coverage                                      |
| 108 | `17-testing/02-integration-tests.md`          | testcontainers                                         |
| 109 | `17-testing/03-e2e-tests.md`                  | Playwright                                             |
| 110 | `17-testing/04-load-tests.md`                 | k6                                                     |
| 111 | `17-testing/05-ai-eval-tests.md`              | promptfoo + DeepEval                                   |
| 112 | `17-testing/06-test-data.md`                  | Fixtures                                               |

### 18 — Coding Standards (6 files)
| #   | File                                          | Purpose                                                |
|-----|-----------------------------------------------|--------------------------------------------------------|
| 113 | `18-coding-standards/00-standards-overview.md` | Tooling + pre-commit                                  |
| 114 | `18-coding-standards/01-python-style.md`      | ruff + mypy + patterns                                 |
| 115 | `18-coding-standards/02-project-layout.md`    | Monorepo rules                                         |
| 116 | `18-coding-standards/03-git-workflow.md`      | Trunk-based + Conventional Commits                     |
| 117 | `18-coding-standards/04-code-review.md`       | Reviewer checklist                                     |
| 118 | `18-coding-standards/05-security.md`          | Secrets, encryption, SAST                              |

### 19 — Roadmap (1 file)
| #   | File                                          | Purpose                                                |
|-----|-----------------------------------------------|--------------------------------------------------------|
| 119 | `19-roadmap.md`                               | 3 phases × 8 weeks, deliverables, acceptance criteria  |

### README (this file)
| #   | File              | Purpose                                                |
|-----|-------------------|--------------------------------------------------------|
| 120 | `README.md`       | This index                                             |

---

## Quick Start

```bash
# 1. Unzip
unzip finance-ai-v3-prompt-package.zip -d finance-ai-v3/

# 2. Open the master prompt
cat finance-ai-v3/00-master-prompt.md

# 3. In MiniMax M3 chat:
#    a. Paste 00-master-prompt.md as system message
#    b. Upload files 01 through 19 in order as user messages
#    c. Send: "Begin Phase 1 execution. Confirm understanding, propose plan for FR-001 to FR-025."
```

## Tech Stack Summary

- **Orchestration:** n8n + Docker Compose / Kubernetes
- **State:** PostgreSQL 16 + Redis 7 (cluster) + Qdrant 1.10
- **LLM Gateway:** LiteLLM (MiniMax M3 primary, GPT-5 / Claude Opus 4 fallback)
- **Service Layer:** FastAPI + Python 3.12 (async)
- **Dashboard:** Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui
- **Observability:** Prometheus + Grafana + Loki + Jaeger + OpenTelemetry
- **Testing:** pytest + testcontainers + Playwright + k6 + promptfoo

## Statistics

- **Files:** 120 markdown
- **Total size:** ~650 KB
- **Estimated word count:** ~150,000 words
- **Estimated printed pages:** ~600
- **Functional Requirements:** 105 (across 3 phases)
- **Non-Functional Requirements:** 60+
- **AI Agents:** 13 (10 LLM-powered, 3 deterministic)
- **Workflows:** 20
- **JSON Schemas:** 10 (+ common sub-schemas)
- **Database tables:** 25+ across 13 schemas
- **Qdrant collections:** 5
- **Redis streams:** 10
- **Dashboard pages:** 10

---

## Notes for the Operator

1. **Read in order.** Files reference earlier files. Skipping ahead may cause confusion.
2. **Master prompt is the constitution.** If any conflict, master prompt wins.
3. **Phase-gated execution.** Do NOT ask the model to do everything at once. Phase 1 first, then 2, then 3.
4. **Iterate on prompts.** Use the backtest agent's weekly report to identify weak prompts; A/B test improvements.
5. **Compliance is non-negotiable.** Every recommendation goes through the compliance agent. No bypassing.
6. **Hallucination guards are hard-coded.** Do NOT remove them even if the model "seems confident".
7. **Cost matters.** Monitor LLM cost daily. If > $20/day, investigate which agent is over-spending.
8. **Backtest weekly.** The system improves only if you act on backtest findings.

---

**End of README.**
