# 03 — Non-Functional Requirements

> **Format:** NFR-ID · Category · Statement · Metric · Target · Measurement

---

## 1. Performance

| ID     | Statement                                                            | Metric                          | Target           | Measurement                |
|--------|----------------------------------------------------------------------|---------------------------------|------------------|----------------------------|
| NFR-P01| Tick-to-DB latency for BIST data                                     | p95 latency                     | < 2 seconds      | OTel traces                |
| NFR-P02| KAP publication to alert latency                                     | p95 latency                     | < 5 minutes      | KAP-to-alert log           |
| NFR-P03| Average decision latency (event → recommendation)                    | p50 latency                     | < 60 seconds     | Decision log               |
| NFR-P04| Decision latency p99                                                 | p99 latency                     | < 5 minutes      | Decision log               |
| NFR-P05| Dashboard page load                                                  | LCP                             | < 1 second       | Lighthouse CI              |
| NFR-P06| Dashboard WebSocket message delivery                                 | p95 latency                     | < 500 ms         | WS monitor                 |
| NFR-P07| LLM call latency                                                     | p95 latency                     | < 8 seconds      | LiteLLM logs               |
| NFR-P08| Vector search (Qdrant) latency                                       | p95 latency                     | < 200 ms         | Qdrant metrics             |
| NFR-P09| PostgreSQL read query latency                                        | p95 latency                     | < 50 ms          | pg_stat_statements         |
| NFR-P10| Redis read latency                                                   | p95 latency                     | < 5 ms           | Redis slowlog              |

## 2. Scalability

| ID     | Statement                                                            | Metric                          | Target           | Measurement                |
|--------|----------------------------------------------------------------------|---------------------------------|------------------|----------------------------|
| NFR-S01| Concurrent tickers monitored                                         | count                           | ≥ 1,000          | Coverage report            |
| NFR-S02| News articles ingested per day                                       | count                           | ≥ 5,000          | News table count           |
| NFR-S03| KAP disclosures processed per day                                    | count                           | ≥ 500            | KAP table count            |
| NFR-S04| Decisions generated per day                                          | count                           | ≥ 1,000          | Decision log count         |
| NFR-S05| Concurrent dashboard users                                           | count                           | ≥ 50             | Load test                  |
| NFR-S06| Horizontal scale-out (add container)                                 | time to effective               | < 2 minutes      | Scaling test               |
| NFR-S07| PostgreSQL storage growth                                            | per year                        | < 500 GB         | Disk monitor               |
| NFR-S08| Qdrant vector count                                                  | count                           | ≥ 10M            | Qdrant stats               |

## 3. Availability & Reliability

| ID     | Statement                                                            | Metric                          | Target           | Measurement                |
|--------|----------------------------------------------------------------------|---------------------------------|------------------|----------------------------|
| NFR-A01| System uptime (excluding planned maintenance)                        | monthly                         | > 99.5%          | Uptime monitor             |
| NFR-A02| Single-component failure recovery                                    | MTTR                            | < 5 minutes      | Chaos exercise             |
| NFR-A03| Data source outage tolerance                                         | degraded mode                   | System continues with cached data, alerts user | Outage simulation |
| NFR-A04| Zero data loss on component failure                                  | lost events per day             | 0                | Dead-letter queue audit    |
| NFR-A05| Email delivery success                                               | deliverability rate             | > 98%            | Email logs                 |
| NFR-A06| Decision record completeness                                         | % decisions with full trace     | 100%             | Audit script               |

## 4. Security

| ID     | Statement                                                            | Metric                          | Target           | Measurement                |
|--------|----------------------------------------------------------------------|---------------------------------|------------------|----------------------------|
| NFR-SE01| Encryption at rest                                                  | algorithm                       | AES-256          | Disk encryption audit      |
| NFR-SE02| Encryption in transit                                              | protocol                        | TLS 1.3          | TLS scan                   |
| NFR-SE03| API authentication                                                 | method                          | JWT (24h)        | Auth log                   |
| NFR-SE04| API authorization                                                  | model                           | RBAC             | Endpoint audit             |
| NFR-SE05| Secret management                                                  | storage                         | Vault / 1Password| Secret scan                |
| NFR-SE06| PII redaction in logs                                              | % PII redacted                  | 100%             | Log scanner                |
| NFR-SE07| SAST scan                                                          | findings (high severity)        | 0                | Bandit + trufflehog        |
| NFR-SE08| Dependency vulnerabilities                                         | CVEs (high+)                    | 0                | pip-audit                  |
| NFR-SE09| API rate limiting                                                  | enforced                        | Yes              | Rate-limit log             |
| NFR-SE10| Audit log immutability                                             | tamper-evident                  | Yes              | Audit log hash chain       |

## 5. Compliance

| ID     | Statement                                                            | Metric                          | Target           | Measurement                |
|--------|----------------------------------------------------------------------|---------------------------------|------------------|----------------------------|
| NFR-C01| Disclaimer on every output                                          | % outputs                       | 100%             | Output scanner             |
| NFR-C02| Decision traceability retention                                     | months                          | ≥ 24             | Retention audit            |
| NFR-C03| Data residency (all data in TR)                                     | regions used                    | TR only          | Infra audit                |
| NFR-C04| SPK (CMB) compliance review                                         | annual                          | Pass             | External audit             |
| NFR-C05| KVKK compliance                                                     | annual                          | Pass             | External audit             |
| NFR-C06| Right to explanation                                               | latency                         | < 24h            | Audit log query            |

## 6. Observability

| ID     | Statement                                                            | Metric                          | Target           | Measurement                |
|--------|----------------------------------------------------------------------|---------------------------------|------------------|----------------------------|
| NFR-O01| Metrics coverage                                                    | % services emitting metrics     | 100%             | Prometheus scrape audit    |
| NFR-O02| Structured logging                                                  | % logs JSON                     | 100%             | Log scanner                |
| NFR-O03| Distributed tracing                                                 | % requests traced               | > 95%            | Jaeger sampling            |
| NFR-O04| Alerting coverage                                                   | % critical paths alerted        | 100%             | Alert audit                |
| NFR-O05| Log retention                                                       | days                            | ≥ 90             | Log storage audit          |
| NFR-O06| Trace retention                                                     | days                            | ≥ 30             | Trace storage audit        |
| NFR-O07| Metric retention                                                    | days                            | ≥ 365            | Metric storage audit       |

## 7. Maintainability

| ID     | Statement                                                            | Metric                          | Target           | Measurement                |
|--------|----------------------------------------------------------------------|-----------------|------------------|----------------------------|
| NFR-M01| Code coverage                                                       | % lines                         | ≥ 80%            | pytest --cov               |
| NFR-M02| Type hint coverage                                                  | % functions                     | 100%             | mypy report                |
| NFR-M03| Lint cleanliness                                                    | errors                          | 0                | ruff                       |
| NFR-M04| Max PR size                                                         | lines changed                   | < 500            | PR template                |
| NFR-M05| Time-to-merge                                                       | median hours                    | < 24             | Git stats                  |
| NFR-M06| Documentation freshness                                            | % FRs linked to docs            | 100%             | Doc audit                  |
| NFR-M07| Schema migration safety                                            | % reversible migrations         | 100%             | Migration review           |

## 8. Cost Efficiency

| ID     | Statement                                                            | Metric                          | Target           | Measurement                |
|--------|----------------------------------------------------------------------|---------------------------------|------------------|----------------------------|
| NFR-CE01| LLM cost per recommendation                                        | USD                             | < $0.50          | LiteLLM cost dashboard     |
| NFR-CE02| Monthly LLM total cost                                             | USD                             | < $500           | LiteLLM cost dashboard     |
| NFR-CE03| Monthly infra cost                                                 | USD                             | < $300           | Cloud billing              |
| NFR-CE04| Cost-per-decision                                                  | USD                             | < $0.80          | Cost / decisions           |

## 9. Data Freshness

| ID     | Statement                                                            | Metric                          | Target           | Measurement                |
|--------|----------------------------------------------------------------------|---------------------------------|------------------|----------------------------|
| NFR-D01| BIST tick freshness                                                 | lag                             | < 2s             | Tick monitor               |
| NFR-D02| KAP freshness                                                       | lag                             | < 5 min          | KAP monitor                |
| NFR-D03| News freshness                                                      | lag                             | < 2 min          | News monitor               |
| NFR-D04| Macro indicator freshness                                           | lag                             | < 1 day          | Macro monitor              |
| NFR-D05| Decision freshness (signal → recommendation)                        | lag                             | < 60s            | Decision monitor           |

## 10. Auditability

| ID     | Statement                                                            | Metric                          | Target           | Measurement                |
|--------|----------------------------------------------------------------------|---------------------------------|------------------|----------------------------|
| NFR-AU01| Every decision has trace                                            | % traced                        | 100%             | Audit script               |
| NFR-AU02| Every evidence item citable                                         | % cited                         | 100%             | Audit script               |
| NFR-AU03| Every LLM call logged                                              | % logged                        | 100%             | LLM log audit              |
| NFR-AU04| Every data source change versioned                                  | % versioned                     | 100%             | Source registry audit      |
| NFR-AU05| Every prompt change versioned                                       | % versioned                     | 100%             | Prompt registry audit      |
