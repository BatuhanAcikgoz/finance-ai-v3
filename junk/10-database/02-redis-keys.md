# 10/02 — Redis Key Schema

> Redis 7 (cluster mode). Used for: cache, pub/sub, streams, DLQ, idempotency keys.

## Key Namespaces

| Pattern                       | Type      | TTL      | Purpose                                |
|-------------------------------|-----------|----------|----------------------------------------|
| `tick:{ticker}:latest`        | hash      | none     | Latest tick (price, volume, ts)        |
| `bar:{ticker}:{tf}:latest`    | hash      | none     | Latest bar for timeframe               |
| `news:hash:{sha256}`          | string    | 30d      | Dedup hash for news articles           |
| `kap:hash:{publishing_id}`    | string    | 90d      | Dedup hash for KAP disclosures         |
| `notif:dedup:{hash}`          | string    | 60min    | Notification dedup                     |
| `notif:ratelimit:{ticker}:{date}` | counter | 24h   | Per-ticker alert rate limit            |
| `idempotency:{workflow}:{key}` | string   | 24h      | Workflow idempotency cache             |
| `sentiment:{ticker}:daily`    | hash      | 7d       | Daily sentiment aggregate              |
| `agent:{name}:state`          | hash      | none     | Agent state (last run, status)         |
| `decision:pending:{decision_id}` | hash  | 5min     | Pending decision (during compliance)   |

## Streams

| Stream                       | Consumer group      | Purpose                                |
|------------------------------|---------------------|----------------------------------------|
| `raw.market.tick`            | `technical_analysis`| Tick events for indicator computation  |
| `raw.market.bar.close`       | `technical_analysis`| Bar close events                       |
| `raw.kap.classified`         | `memory_indexer`, `fundamental_analysis` | KAP after classification |
| `raw.news.new`               | `news_analysis`     | New articles                           |
| `raw.macro.update`           | `macro_analysis`    | New macro indicator                    |
| `analysis.technical.complete`| `supervisor`        | Technical signal ready                 |
| `analysis.fundamental.complete` | `supervisor`     | Fundamental signal ready               |
| `decision.created`           | `compliance_check`  | New decision awaiting compliance       |
| `decision.approved`          | `notification_dispatch` | Approved for dispatch             |
| `report.generated`           | `notification_dispatch` | Report ready to send              |

## Pub/Sub Channels

| Channel                | Subscribers                   | Purpose                          |
|------------------------|-------------------------------|----------------------------------|
| `trigger.scheduler.*`  | All collectors                | Scheduler triggers               |
| `dashboard.broadcast`  | WebSocket gateway             | Push to dashboard clients        |
| `alert.critical`       | notification_dispatch         | CRITICAL severity alerts         |

## Dead Letter Queue

- Stream `dlq.events` for failed events
- Each entry: `{original_stream, original_id, payload, error, failed_at}`
- Replay worker retries after fix; manual trigger required
