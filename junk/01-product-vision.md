# 01 — Product Vision

> **Status:** Authoritative. All other documents MUST align with this vision.
> **Audience:** Engineers, product managers, compliance officers, investors.

---

## 1. Problem Definition

Turkish capital markets produce an overwhelming volume of heterogeneous information every trading day: BIST tick-by-tick price updates across 500+ equities, KAP disclosures (financial reports, dividend announcements, material events, board decisions), TEFAS fund NAV movements for hundreds of investment funds, breaking news from dozens of Turkish and international outlets, macroeconomic releases from TCMB and TÜİK, and sector bulletins from BDDK. A single retail or semi-professional investor cannot read, correlate, and act on this information in real time. Existing tools fall into three categories, all of which are insufficient:

1. **Brokerage platforms** (Matriks, İMKBticker, Foreks) — provide raw data and basic technical indicators, but no autonomous analysis, no cross-source correlation, no memory of past decisions, and no explainable recommendations.
2. **News aggregators** (Bloomberg HT, Foreks News, investing.com.tr) — surface headlines but do not connect them to portfolio impact, do not assess source reliability, and do not deduplicate near-identical stories.
3. **Robo-advisors** — typically only do periodic rebalancing based on risk questionnaires; they do not perform daily fundamental re-evaluation, do not read KAP filings, and do not adapt to breaking macroeconomic events.

The result is that even sophisticated Turkish investors miss 60–80% of actionable signals on any given day, react late to material disclosures, and make decisions based on a single technical indicator rather than a multi-evidence synthesis.

## 2. Vision

**Finance AI V3 transforms the overwhelming complexity of Turkish financial markets into clear, explainable, evidence-based investment intelligence through autonomous artificial intelligence.**

Finance AI V3 is an always-on, multi-agent system that reads every signal source in parallel, reasons about each signal in the context of the user's portfolio, aggregates evidence across technical, fundamental, macro, news, sentiment, sector, and historical-similarity dimensions, and emits a small number of high-confidence, explainable recommendations per day. The system remembers its past decisions, scores its own accuracy via backtesting, and continuously recalibrates its confidence model.

## 3. Target Users

| Segment               | Description                                                                                         | Primary need                                                       |
|-----------------------|-----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------|
| Active retail trader  | Trades 5–20 BIST stocks monthly, holds 50M–500M TRY portfolio                                      | Daily briefing with 3–5 actionable, ranked, risk-adjusted ideas    |
| Semi-professional PM  | Manages 500M–5B TRY, family office or HNW client base                                              | Compliance-aware decisions, decision traceability, audit trail     |
| Buy-side analyst      | Produces research notes for an institutional desk                                                   | Pre-filtered universe, evidence packs, draft research notes        |
| Sell-side compliance  | Reviews recommendations before they reach clients                                                   | Audit log of every signal and decision, evidence citation          |

## 4. User Personas

### 4.1 Persona A — "Mert" (active retail trader, 38)
- Holds 12 BIST stocks, 3 TEFAS funds, 200M TRY total
- Trades 2–4 times per week based on technical + news
- Pain: spends 90 minutes every morning reading KAP and news; misses half the disclosures that affect his holdings; reacts to MACD crosses without checking fundamentals
- Success criterion: reads Finance AI V3 morning briefing in 5 minutes, executes 0–2 trades based on ranked recommendations, has full audit trail of why each recommendation was made

### 4.2 Persona B — "Selin" (family office PM, 45)
- Manages 1.2B TRY across 35 holdings for 4 HNW families
- Must produce weekly investment committee report
- Pain: 8 hours every Sunday assembling the report; cannot quickly answer "why did we hold X last quarter?"
- Success criterion: weekly report auto-drafted from decision log; investment committee approves in 30 minutes

### 4.3 Persona C — "Burak" (buy-side analyst, 32)
- Covers 80 BIST stocks across 5 sectors
- Pain: cannot read all KAP disclosures in time; produces 3 research notes per week
- Success criterion: Finance AI V3 surfaces the 5 most material KAP events of the day for his universe, drafts a 200-word note for each, he reviews and publishes 8 notes per week

### 4.4 Persona D — "Ayşe" (compliance officer, 41)
- Must review every outgoing recommendation
- Pain: 200+ recommendations per day across the desk; cannot check evidence for each
- Success criterion: every recommendation has a clickable decision trace; she samples 10 per day; system auto-flags any decision that violates compliance rules

## 5. Scope

### In Scope (V3)
- BIST equities, BIST ETFs, TEFAS mutual/participation/gold/index funds
- KAP disclosures (all categories)
- News from 12 pre-approved Turkish sources + 5 international sources
- TCMB, TÜİK, BDDK macro indicators
- Technical analysis (40+ indicators)
- Fundamental analysis (financial statements, ratios, peer comparison)
- Risk modeling (VaR, CVaR, beta, correlation)
- Multi-portfolio support (up to 10 portfolios per user)
- Daily/weekly/monthly briefing emails
- Realtime dashboard with WebSocket push
- Decision traceability with 2-year retention

### Out of Scope (V3 — deferred to V4+)
- Crypto assets (BTC, USDT-TRY)
- Foreign equities (US, EU)
- Derivatives (VIOP futures/options)
- Direct order execution (only recommendations, no broker integration)
- Mobile app (web dashboard only)
- Multi-tenant SaaS (single-user deployment first)

## 6. Goals

| #    | Goal                                                                                       | Measurement                                  |
|------|--------------------------------------------------------------------------------------------|----------------------------------------------|
| G-1  | Cover ≥ 95% of BIST-100 by market cap with daily analysis                                  | Daily coverage report                        |
| G-2  | Detect ≥ 98% of KAP material disclosures within 5 minutes of publication                   | Disclosure-to-alert latency monitoring       |
| G-3  | Produce ≥ 80% confidence on every emitted recommendation                                   | Distribution of confidence scores            |
| G-4  | Achieve ≤ 5% false-alert rate (alerts that, in hindsight, were not actionable)             | Weekly backtest + manual sampling            |
| G-5  | Deliver daily briefing by 08:30 TRT every trading day                                      | Email send-time log                          |
| G-6  | Maintain decision traceability for 100% of recommendations, 2-year retention               | Trace storage audit                          |
| G-7  | Recover from any single-component failure within 5 minutes                                 | Chaos engineering exercises                  |
| G-8  | Operate at < $500/month LLM cost for the full pipeline                                     | LiteLLM cost dashboard                       |

## 7. Non-Goals

1. **No automatic trading.** Finance AI V3 never places orders. It only recommends; the user clicks "execute" in their broker.
2. **No personalized investment advice.** Recommendations are portfolio-aware but not lifestyle- or tax-aware.
3. **No prediction guarantees.** The system never claims to predict prices; it only estimates probability distributions and confidence.
4. **No multi-language UI in V3.** Turkish UI only; English only in JSON keys.
5. **No mobile application.** Web dashboard only.
6. **No real-time news publishing.** The system consumes news; it does not publish.

## 8. Success Metrics

| Metric                                | Target         | Measurement window | Source                  |
|---------------------------------------|----------------|--------------------|-------------------------|
| Market coverage                       | > 95%          | Daily              | Coverage report         |
| Critical event detection              | > 98%          | Daily              | KAP-to-alert log        |
| Duplicate news rate                   | < 3%           | Daily              | News dedup audit        |
| Daily uptime                          | > 99.5%        | Monthly            | Uptime monitor          |
| Average analysis latency              | < 60 seconds   | Daily p50          | OTel traces             |
| Average recommendation confidence     | > 80%          | Weekly             | Decision log            |
| False alert rate                      | < 5%           | Weekly             | Backtest + manual review|
| Decision trace completeness           | 100%           | Daily              | Audit script            |
| Daily briefing on-time delivery       | > 99%          | Monthly            | Email send log          |
| Backtesting hit rate (≥ 80% conf.)    | > 60%          | Monthly            | Backtest report         |

## 9. KPIs (Leading Indicators)

- LLM call success rate (target > 99%)
- LLM call p95 latency (target < 8s)
- Schema validation pass rate (target 100%)
- Workflow retry rate (target < 5%)
- Vector search recall@10 (target > 0.85)
- Dashboard WebSocket message loss (target 0)
- Email deliverability (target > 98%)
- Cost per recommendation (target < $0.50)

## 10. Product Philosophy

Finance AI V3 is built on five principles that take precedence over feature velocity:

1. **Evidence over opinion.** Every claim cites its sources. Every recommendation is the output of an evidence-aggregation function, not a single LLM call's "feeling".
2. **Multiple confirmations over a single signal.** No RSI cross, no single KAP disclosure, no single news headline is enough to recommend an action. At least three independent evidence streams must agree.
3. **Never hallucinate missing data.** If a fundamental ratio cannot be computed because the company hasn't yet filed quarterly results, the system says so explicitly and downgrades confidence.
4. **Always disclose uncertainty.** Every recommendation includes a confidence score, an uncertainty band, and a contradiction score. Hiding uncertainty is a defect.
5. **Compliance by design.** Every recommendation includes a disclaimer. Every decision is logged. Every piece of evidence is citable. The system is auditable end-to-end.

## 11. Data Sources

| Source                            | Type           | Refresh        | Coverage                                     | Owner workflow        |
|-----------------------------------|----------------|----------------|----------------------------------------------|-----------------------|
| BIST intraday prices              | REST + WS      | Real-time      | All BIST equities + ETFs                     | market_collector      |
| TEFAS fund NAV                    | HTML scrape    | End of day     | All public funds                             | tefas_collector       |
| KAP disclosures                   | REST           | Every 5 min    | All listed companies                         | kap_collector         |
| News (Bloomberg HT, AA, Foreks, Reuters, Bloomberg, CNBC-e, Dünya, Capital, Para, Ekonomim, PwC Türkiye, Bigpara) | RSS + scrape | Every 2 min | Major Turkish + intl financial news | news_collector |
| TCMB indicators                   | REST (EVDS)    | Daily          | Policy rate, FX reserves, money supply, CPI  | macro_collector       |
| TÜİK indicators                   | REST           | Monthly        | CPI, PPI, unemployment, GDP                  | macro_collector       |
| BDDK bulletins                    | PDF scrape     | Weekly         | Sector capital adequacy, NPL ratios          | macro_collector       |
| Company financial statements      | KAP scrape     | Quarterly      | All listed companies                         | fundamental_analysis  |
| Historical price series           | BIST archive   | Daily          | 10-year price history                        | technical_analysis    |

## 12. Product Pillars

Finance AI V3 stands on six pillars:

1. **Continuous Market Monitoring** — never stops. 24/7 ingestion, 24/5 trading-hours analysis, weekend batch backtests.
2. **Autonomous Research** — agents proactively fetch additional information when evidence is insufficient; they don't just answer queries.
3. **Explainable Decisions** — every recommendation can be unwound to its atomic evidence; no black-box outputs.
4. **Historical Memory** — the system remembers past analyses, news, recommendations, and outcomes; uses them to score confidence on new decisions.
5. **Portfolio Awareness** — every recommendation is contextualized against the user's actual holdings, exposure, and risk budget.
6. **Risk Awareness** — every recommendation includes risk metrics (volatility, VaR contribution, beta to BIST100) and confidence-weighted position sizing.

## 13. Product Principles (Engineering)

The platform must be:
- **Modular** — every component replaceable without touching others.
- **Scalable** — horizontal scaling by adding containers, never by re-architecting.
- **Observable** — every action emits metrics, logs, traces.
- **Explainable** — every output has a decision trace.
- **Fault-Tolerant** — single-component failure does not stop the system.
- **Cost-Efficient** — LLM cost per recommendation < $0.50.
- **AI-First** — agents are first-class citizens, not bolted on.
- **Schema-First** — schemas are the contract; code is generated from them.
- **Event-Driven** — components communicate via events, not RPCs.
- **Cloud-Ready** — runs anywhere with Docker; no cloud-vendor lock-in.
- **Self-Improving** — backtests feed into prompt and weight tuning.
- **Provider-Agnostic** — LLM, vector DB, and broker can be swapped.

## 14. Decision Philosophy

A recommendation NEVER depends on a single signal. The decision engine aggregates 8 evidence streams:

```
Technical Analysis     ─┐
Fundamental Analysis   ─┤
Macroeconomics         ─┤
News & Sentiment       ─┤
KAP Disclosures        ─┼──►  Decision Engine  ──►  {action, confidence, evidence[], trace_id}
Sector Performance     ─┤
Portfolio Exposure     ─┤
Historical Similarity  ─┘
```

Each stream produces a `{signal, strength, confidence}` triple. The decision engine computes a weighted aggregate (weights learned from backtests), applies portfolio-aware filters, and emits the final recommendation.

## 15. Trust Model

Every recommendation includes:

| Field                  | Type      | Meaning                                                     |
|------------------------|-----------|-------------------------------------------------------------|
| `confidence`           | float 0–1 | Probability the recommendation is correct                   |
| `importance`           | enum      | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`                         |
| `novelty`              | float 0–1 | 1 = brand-new signal, 0 = same as yesterday                 |
| `risk`                 | enum      | `LOW`, `MEDIUM`, `HIGH`, `EXTREME`                          |
| `expected_impact`      | float     | Expected % move on the position over horizon                |
| `evidence_count`       | int       | Number of independent evidence items                        |
| `data_freshness`       | enum      | `REAL_TIME`, `INTRADAY`, `EOD`, `STALE`                     |
| `source_reliability`   | float 0–1 | Mean reliability of evidence sources                        |
| `contradiction_score`  | float 0–1 | 0 = all evidence agrees, 1 = strongly contradictory         |

## 16. Daily Workflow

```
07:30 TRT  Pre-market analysis: overnight news, KAP from previous evening, TCMB releases
           │
08:00 TRT  Market opens (pre-open auction starts 09:45, continuous trading 10:00)
           │
10:00–18:00 Continuous monitoring: tick data, intraday alerts, news stream
           │
           ├─ Critical alert triggers immediate email + dashboard push
           ├─ Portfolio drift triggers rebalance suggestion
           └─ Periodic re-scoring every 5 minutes during trading
           │
18:00 TRT  Market closes
           │
18:30 TRT  End-of-day analysis: full re-run of all agents on day's data
           │
19:00 TRT  Evening summary email sent
           │
Friday     Weekly summary email
Last day   Monthly report
```

## 17. Product Identity

Finance AI V3 is:
- ❌ NOT a chatbot
- ❌ NOT a stock screener
- ❌ NOT a news summarizer
- ❌ NOT a robo-advisor
- ❌ NOT a trading bot

Finance AI V3 IS an autonomous, multi-agent, evidence-aggregating, explainable financial research analyst for Turkish capital markets.

## 18. Long-Term Vision (3–5 years)

Evolve into an institutional-grade financial intelligence platform capable of:
- Research — autonomous generation of research notes
- Analysis — multi-dimensional (technical, fundamental, macro, sentiment, sector)
- Memory — 10+ years of decisions, outcomes, and lessons learned
- Risk Modeling — scenario simulation, stress testing, Monte Carlo
- Portfolio Intelligence — multi-portfolio, multi-strategy, multi-custodian
- Market Surveillance — anomaly detection, manipulation flags, circuit-breaker prediction
- Decision Support — what-if analysis, scenario comparison, attribution
- Scenario Simulation — interest-rate shocks, geopolitical events, sector rotation
- Knowledge Discovery — pattern mining across historical decisions
- Eventually: the central AI analyst for institutional investors in Turkish financial markets

## 19. Vision Statement

> **Finance AI V3 transforms the overwhelming complexity of Turkish financial markets into clear, explainable, evidence-based investment intelligence through autonomous artificial intelligence.**

## 20. Differentiators (vs. existing tools)

| Differentiator           | Finance AI V3                                       | Typical tool                         |
|--------------------------|-----------------------------------------------------|--------------------------------------|
| Decision explanation     | Full evidence trace with citations                  | "RSI > 70"                           |
| Multi-evidence synthesis | 8 streams, weighted aggregate                       | Single indicator                     |
| Memory                   | Qdrant-backed, 2-year retention                     | None                                 |
| KAP-aware                | Reads every KAP within 5 min                        | Manual check                         |
| Portfolio-aware          | Every rec contextualized to holdings                | Generic                              |
| Backtesting              | Weekly automated, feeds into confidence calibration | None                                 |
| Compliance               | Built-in agent + disclaimer on every output         | Afterthought                         |
| Decision traceability    | 100% of decisions, 2-year retention                 | None                                 |
| Provider-agnostic        | LiteLLM, swap models in config                      | Hard-coded to one provider           |
