# 16/01 — Metrics

## Application Metrics

### Business
- `decisions_created_total{action, compliance_status}`
- `decisions_confidence_bucket{bucket}` (histogram)
- `evidence_collected_total{stream}`
- `alerts_sent_total{severity, channel}`
- `reports_generated_total{type}`
- `backtest_hit_rate` (gauge)
- `portfolio_var_pct` (gauge, per portfolio)

### Workflow
- `workflow_duration_seconds{workflow_id}` (histogram)
- `workflow_step_failures_total{workflow_id, step_id}`
- `workflow_retries_total{workflow_id}`
- `workflow_queue_depth` (gauge)

### Agent
- `agent_duration_seconds{agent_name}` (histogram)
- `agent_llm_tokens_total{agent_name, direction=in|out}`
- `agent_failures_total{agent_name, reason}`
- `agent_cost_usd_total{agent_name}` (counter)

### LLM
- `llm_call_duration_seconds{provider, model}` (histogram)
- `llm_call_failures_total{provider, model, status_code}`
- `llm_tokens_total{provider, model, direction}` (counter)
- `llm_cost_usd_total{provider, model}` (counter)
- `llm_circuit_breaker_state{provider}` (gauge: 0=closed, 1=open)

### Data Ingestion
- `ingest_latency_seconds{source}` (histogram)
- `ingest_records_total{source}`
- `ingest_failures_total{source, reason}`
- `ingest_queue_depth{source}` (gauge)

### Infrastructure
- `http_request_duration_seconds{service, route, method}` (histogram)
- `http_requests_total{service, route, method, status}`
- `redis_operations_total{operation}`
- `redis_latency_seconds{operation}` (histogram)
- `postgres_connections` (gauge)
- `postgres_query_duration_seconds` (histogram)
- `qdrant_search_duration_seconds` (histogram)
- `qdrant_insert_duration_seconds` (histogram)
- `process_cpu_seconds_total{service}`
- `process_resident_memory_bytes{service}`

## Prometheus Scrape Config

```yaml
scrape_configs:
  - job_name: 'finance-ai-v3'
    static_configs:
      - targets:
        - 'api-gateway:8000'
        - 'market-collector:8000'
        - 'kap-collector:8000'
        - 'news-collector:8000'
        - 'tefas-collector:8000'
        - 'macro-collector:8000'
        - 'supervisor:8000'
        - 'decision-engine:8000'
        - 'risk-engine:8000'
        - 'report-generator:8000'
        - 'notification-dispatch:8000'
        - 'backtest-runner:8000'
        - 'compliance-checker:8000'
    metrics_path: /metrics
    scrape_interval: 15s
```

## Grafana Dashboards

| Dashboard                  | Panels                                                              |
|----------------------------|---------------------------------------------------------------------|
| System Overview            | Golden signals per service                                          |
| Decision Pipeline          | Decisions created, confidence dist, compliance rate                 |
| Agent Activity             | Per-agent calls, latency, cost, success rate                        |
| LLM Costs                  | Daily/monthly cost by provider/model, tokens                        |
| Data Ingestion             | Per-source latency, throughput, errors                              |
| Risk                       | Portfolio VaR time series, beta, HHI                                |
| Alerts                     | Alerts sent by severity, false alert rate                           |
| Backtest Performance       | Hit rate over time, calibration                                     |
