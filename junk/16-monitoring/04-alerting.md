# 16/04 — Alerting

## Alertmanager Routes

| Alert                              | Severity  | Route                                        |
|------------------------------------|-----------|----------------------------------------------|
| PostgreSQL primary down            | CRITICAL  | PagerDuty + Slack #ops                       |
| Redis cluster unavailable          | CRITICAL  | PagerDuty + Slack #ops                       |
| LiteLLM all providers down         | CRITICAL  | PagerDuty + Slack #ops                       |
| n8n down                           | CRITICAL  | PagerDuty                                    |
| Decision queue depth > 100         | WARN      | Slack #ops                                   |
| LLM error rate > 5%                | WARN      | Slack #ai                                    |
| Schema validation failures > 10    | WARN      | Slack #engineering                           |
| Daily briefing not sent by 09:00   | CRITICAL  | PagerDuty + Slack #product                   |
| Cost > $20/day on LLM              | WARN      | Slack #ai                                    |
| Backtest hit rate < 50%            | WARN      | Slack #ai                                    |
| Backtest hit rate < 40%            | CRITICAL  | PagerDuty + Slack #ai                        |
| Disk > 80% full                    | WARN      | Slack #ops                                   |
| Disk > 95% full                    | CRITICAL  | PagerDuty + Slack #ops                       |

## Alert Rules (PromQL)

```yaml
groups:
  - name: finance-ai-v3.rules
    rules:
      - alert: PostgreSQLPrimaryDown
        expr: pg_up{instance="postgres-primary"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL primary is down"
      
      - alert: LLMErrorRateHigh
        expr: |
          rate(llm_call_failures_total[5m]) / rate(llm_call_duration_seconds_count[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "LLM error rate > 5%"
      
      - alert: DecisionQueueDepthHigh
        expr: workflow_queue_depth{workflow_id="decision_engine"} > 100
        for: 2m
        labels:
          severity: warning
      
      - alert: DailyBriefingNotSent
        expr: |
          (hour() == 9 and minute() > 0) and
          reports_generated_total{type="MORNING_BRIEFING"} offset 1d == reports_generated_total{type="MORNING_BRIEFING"}
        labels:
          severity: critical
```

## On-Call Rotation

- PagerDuty schedule: 1 primary + 1 secondary
- Weekly rotation (Monday 09:00 TRT handoff)
- ACK required within 5 min; resolve within 60 min
