# 16/02 — Logging

## Format: JSON

```json
{
  "timestamp": "2026-07-28T10:30:00.123+03:00",
  "level": "info",
  "service": "decision-engine",
  "message": "Decision created",
  "decision_id": "uuid",
  "ticker": "THYAO",
  "action": "BUY",
  "confidence": 0.75,
  "trace_id": "abc123",
  "span_id": "def456",
  "user_id": null,
  "workflow_id": "decision_engine",
  "idempotency_key": "decision:p-default:THYAO:2026-07-28T10:30:00+03:00"
}
```

## Levels

| Level    | Use                                                              |
|----------|------------------------------------------------------------------|
| DEBUG    | Detailed flow (dev only)                                         |
| INFO     | Normal operations (decisions, alerts, reports)                  |
| WARN     | Recoverable issues (retries, fallbacks)                         |
| ERROR    | Failures (failed LLM call, DB write fail)                       |
| CRITICAL | System-down events (postgres primary down, Redis cluster down)  |

## Library: structlog

```python
import structlog
log = structlog.get_logger()

log.info("decision_created",
         decision_id=d.id,
         ticker=d.ticker,
         action=d.action,
         confidence=d.confidence)
```

## Log Shipping

- Promtail tails container logs (Docker `/var/lib/docker/containers/*/*.log`)
- Ships to Loki
- Loki indexes by `{service, level}` labels
- Query: `{service="decision-engine"} |= "ERROR" | json`

## PII Redaction

- On ingest, scan for email/phone/IBAN patterns; redact with `[REDACTED]`
- KAP disclosure bodies NOT logged in full (too sensitive); only metadata
- LLM prompts/completions logged but with PII redacted
