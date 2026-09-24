# 19 — Roadmap

> 3 phases × 8 weeks = 24 weeks total. Each phase has clear goals, deliverables, and acceptance criteria.

---

## Phase 1 — MVP (Weeks 1–8)

### Goal
Prove the data pipeline end-to-end with one ticker (THYAO). Daily briefing email with technical + news analysis.

### Deliverables

| Week | Deliverable                                                              |
|------|--------------------------------------------------------------------------|
| 1    | Project scaffolding (uv, Docker Compose, CI/CD pipeline, schemas)        |
| 2    | PostgreSQL + Redis + Qdrant running; migrations applied                  |
| 3    | Market collector (FR-001 to FR-005) for THYAO only                       |
| 4    | KAP collector (FR-008 to FR-010) for THYAO                               |
| 5    | News collector (FR-011 to FR-013)                                        |
| 6    | Technical analysis workflow (FR-024, FR-025); 40+ indicators            |
| 7    | Report generator + email system (FR-051, FR-052)                         |
| 8    | Dashboard skeleton (login, overview, decisions list); smoke tests        |

### Acceptance Criteria

- [ ] THYAO tick data flows from BIST API → PostgreSQL → dashboard in < 2s
- [ ] THYAO KAP disclosures classified and emailed within 5 min of publication
- [ ] Daily morning briefing arrives by 08:30 TRT with THYAO technical + news analysis
- [ ] Dashboard shows live price + last 5 decisions
- [ ] All FR-001 to FR-025 tests pass

### Risks

| Risk                                | Mitigation                                          |
|-------------------------------------|-----------------------------------------------------|
| BIST API access delayed             | Start with public BIST website scrape as fallback   |
| KAP API rate limits                 | Apply for higher quota early; cache aggressively    |
| LiteLLM integration complexity      | Use OpenAI provider first; add MiniMax in Phase 2   |

---

## Phase 2 — Production (Weeks 9–16)

### Goal
95% market coverage, multi-agent decision pipeline, full dashboard, < 60s decision latency.

### Deliverables

| Week  | Deliverable                                                              |
|-------|--------------------------------------------------------------------------|
| 9     | Scale market collector to all BIST-100 (FR-001 to FR-005)                |
| 10    | TEFAS collector (FR-006, FR-007); macro collector (FR-014 to FR-016)    |
| 11    | Fundamental analysis agent + workflow (FR-026 to FR-028)                 |
| 12    | Macro analysis agent (FR-029, FR-030); news analysis agent (FR-031)     |
| 13    | Sentiment analysis agent (FR-032); sector analysis agent (FR-033, FR-034)|
| 14    | Qdrant integration; memory indexer (FR-035, FR-036); supervisor agent   |
| 15    | Decision engine (FR-039, FR-047, FR-048); risk engine (FR-042 to FR-044)|
| 16    | Portfolio engine (FR-040, FR-041, FR-046); notification dispatch (FR-049, FR-050) |

### Acceptance Criteria

- [ ] All BIST-100 tickers covered with daily analysis
- [ ] TEFAS funds (800+) ingested daily
- [ ] Multi-agent pipeline produces decisions with ≥ 3 evidence streams
- [ ] Average decision latency < 60s (p50)
- [ ] Decision traceability 100% (every decision has evidence[] with source_id)
- [ ] All FR-026 to FR-070 tests pass

### Risks

| Risk                                | Mitigation                                          |
|-------------------------------------|-----------------------------------------------------|
| LLM cost exceeds $500/month         | Use MiniMax M3 (cheaper); cache aggressively; use deterministic engines where possible |
| Decision latency > 60s              | Parallelize specialist agents; cache results        |
| Qdrant scaling issues               | Start with single node; plan cluster for Phase 3    |
| KAP classification accuracy < 90%   | Fine-tune prompt; add few-shot examples             |

---

## Phase 3 — Optimization (Weeks 17–24)

### Goal
Institutional-grade reliability, backtesting, compliance hardening, cost optimization, multi-portfolio.

### Deliverables

| Week  | Deliverable                                                              |
|-------|--------------------------------------------------------------------------|
| 17    | Compliance agent (FR-091, FR-092); backtest agent (FR-072 to FR-074)     |
| 18    | Backtest runner workflow; weekly backtest reports                        |
| 19    | Weight recalibration pipeline (FR-074); prompt A/B testing (FR-080)      |
| 20    | Security hardening (FR-094 to FR-100); 2FA; RBAC                         |
| 21    | Multi-portfolio support (FR-046); portfolio editor in dashboard          |
| 22    | Realtime WebSocket push for dashboard (FR-059); alert inbox (FR-064)     |
| 23    | Monitoring + observability stack (Prometheus, Loki, Jaeger)              |
| 24    | Load testing; chaos engineering; DR exercise; production cutover         |

### Acceptance Criteria

- [ ] Weekly backtest runs automatically; hit-rate displayed on dashboard
- [ ] Compliance agent blocks 100% of decisions with forbidden language
- [ ] All data encrypted at rest (AES-256) and in transit (TLS 1.3)
- [ ] RBAC enforced on every endpoint
- [ ] Multi-portfolio (up to 10 per user) working
- [ ] WebSocket push works with 50 concurrent users, 0 message loss
- [ ] p95 API latency < 200ms under 1000 RPS load
- [ ] Recovery from single-component failure < 5 min
- [ ] Monthly LLM cost < $500
- [ ] All FR-071 to FR-105 tests pass

### Risks

| Risk                                | Mitigation                                          |
|-------------------------------------|-----------------------------------------------------|
| Compliance officer availability     | Engage compliance consultant early                  |
| Backtest reveals poor performance   | Iterate on prompts; recalibrate weights             |
| Load test reveals bottlenecks       | Profile + optimize; horizontal scaling              |
| Chaos exercise finds SPOF           | Architectural fix; re-run exercise                  |

---

## Post-V3 (Future)

- Crypto assets (BTC, USDT-TRY)
- Foreign equities (US, EU)
- Derivatives (VIOP)
- Mobile app (React Native)
- Multi-tenant SaaS
- Direct broker integration (order execution)
- International expansion (other emerging markets)

---

## Total Effort Estimate

| Phase    | Duration | Engineers (full-time) | Total eng-weeks |
|----------|----------|------------------------|------------------|
| Phase 1  | 8 weeks  | 2                      | 16               |
| Phase 2  | 8 weeks  | 3                      | 24               |
| Phase 3  | 8 weeks  | 3                      | 24               |
| **Total**| **24 weeks** | **Avg 2.7**       | **64**           |

Plus part-time:
- Product manager: 8 hours/week
- Designer: 4 hours/week
- Compliance consultant: 4 hours/week
- DevOps: 8 hours/week

---

## Success Definition

Finance AI V3 is "done" when:

1. All 105 FRs pass acceptance
2. All NFRs meet targets
3. System runs for 30 days in production with > 99.5% uptime
4. Weekly backtest shows hit rate > 60% on ≥ 0.8-confidence decisions
5. Monthly LLM cost < $500
6. Compliance audit passes
7. 5+ active users using daily for 30 days

After "done", the system enters continuous-improvement mode:
- Weekly prompt iterations based on backtest
- Monthly new data sources
- Quarterly architecture review
- Annual compliance audit
