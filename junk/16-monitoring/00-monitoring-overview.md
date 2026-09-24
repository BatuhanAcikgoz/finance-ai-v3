# 16 — Monitoring Overview

> Three pillars: metrics (Prometheus + Grafana), logs (Loki + Promtail), traces (Jaeger + OTel Collector).

## Stack

| Component           | Purpose                            | Retention |
|---------------------|------------------------------------|-----------|
| Prometheus          | Metrics scraping + storage         | 365 days  |
| Grafana             | Dashboards                         | N/A       |
| Loki                | Log aggregation                    | 90 days   |
| Promtail            | Log shipper                        | N/A       |
| Jaeger              | Distributed tracing                | 30 days   |
| OTel Collector      | Trace collection                   | N/A       |
| Alertmanager        | Alert routing                      | N/A       |

## Golden Signals (per service)

1. **Latency:** p50, p95, p99
2. **Traffic:** requests/sec, messages/sec
3. **Errors:** error rate, error count by code
4. **Saturation:** CPU, memory, disk, queue depth
