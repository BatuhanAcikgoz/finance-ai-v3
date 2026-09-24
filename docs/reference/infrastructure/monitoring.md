# Monitoring ve Alerting

Finance AI V3 için izleme ve uyarı sistemi.

## 📋 İçindekiler

1. [Genel Bakış](#genel-bakış)
2. [Prometheus Metrikleri](#prometheus-metrikleri)
3. [Grafana Dashboard](#grafana-dashboard)
4. [Tracing](#tracing)
5. [Logging](#logging)
6. [Alerting](#alerting)

---

## Genel Bakış

```
┌─────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY STACK                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│   │ Prometheus   │    │  Grafana    │    │   Jaeger     │      │
│   │  Metrics     │◄──►│ Dashboards  │    │   Tracing    │      │
│   └──────┬───────┘    └──────────────┘    └──────────────┘      │
│          │                                                        │
│          ▼                                                        │
│   ┌──────────────┐                                               │
│   │    Loki      │                                               │
│   │   Logs      │                                               │
│   └──────────────┘                                               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Erişim Bilgileri

| Servis | URL | Kullanıcı | Şifre |
|--------|-----|-----------|-------|
| Grafana | http://localhost:3001 | admin | (GRAFANA_PASSWORD) |
| Prometheus | http://localhost:9090 | - | - |
| Jaeger | http://localhost:16686 | - | - |

---

## Prometheus Metrikleri

### Ana Metrikler

| Metrik | Tip | Açıklama |
|--------|-----|----------|
| `http_requests_total` | Counter | Toplam HTTP istekleri |
| `http_request_duration_seconds` | Histogram | İstek süresi |
| `http_requests_in_progress` | Gauge | Devam eden istekler |
| `db_pool_connections_total` | Gauge | Veritabanı bağlantıları |
| `redis_commands_total` | Counter | Redis komutları |
| `active_decisions_total` | Gauge | Aktif kararlar |
| `analysis_duration_seconds` | Histogram | Analiz süresi |
| `data_collection_duration_seconds` | Histogram | Veri toplama süresi |

### Custom Metrikler

```python
from prometheus_client import Counter, Histogram, Gauge

# Metrikler
http_requests = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

active_decisions = Gauge(
    'active_decisions_total',
    'Number of active decisions'
)

analysis_duration = Histogram(
    'analysis_duration_seconds',
    'Analysis duration in seconds',
    ['analysis_type']
)
```

---

## Grafana Dashboard

### Dashboard: Finance AI V3 Overview

**ID**: `finance-ai-v3-overview`

#### Paneller

1. **Request Rate**
   - Grafik tipi: Time series
   - Sorgu: `rate(http_requests_total[5m])`

2. **Error Rate**
   - Grafik tipi: Time series
   - Sorgu: `rate(http_requests_total{status=~"5.."}[5m])`

3. **Latency Percentiles (p50, p95, p99)**
   - Grafik tipi: Time series
   - Sorgu: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`

4. **Database Connections**
   - Grafik tipi: Stat
   - Sorgu: `db_pool_connections`

5. **Active Decisions**
   - Grafik tipi: Time series
   - Sorgu: `active_decisions_total`

6. **Cache Hit Rate**
   - Grafik tipi: Gauge
   - Sorgu: `redis_commands_total{cmd="hit"} / redis_commands_total`

---

## Tracing

### Jaeger Configuration

```yaml
# OpenTelemetry Collector config
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [jaeger]
```

### Trace Örneği

```
Span: decision_engine.make_decision
├─ Span: fetch_latest_analysis
│  ├─ Span: fetch_technical_analysis (15ms)
│  ├─ Span: fetch_fundamental_analysis (45ms)
│  ├─ Span: fetch_sentiment (20ms)
│  └─ Span: fetch_sector_analysis (18ms)
├─ Span: aggregate_evidence (5ms)
├─ Span: compute_confidence (2ms)
├─ Span: determine_action (1ms)
└─ Span: insert_decision (12ms)
```

---

## Logging

### Loki Configuration

```yaml
# loki.yml
auth_enabled: false

server:
  http_listen_port: 3100

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2024-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h
```

### Log Formatı

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "service": "decision_engine",
  "message": "decision_made",
  "decision_id": "550e8400-e29b-41d4-a716-446655440000",
  "ticker": "THYAO",
  "action": "BUY",
  "confidence": 0.75,
  "trace_id": "abc123",
  "span_id": "def456"
}
```

### Log sorguları

```logql
# Tüm error logları
{service=~".+"} |= "ERROR"

# Belirli servis logları
{service="decision_engine"}

# Trace ID ile logları bul
{service="decision_engine"} | json | trace_id="abc123"

# Son 5 dakikadaki error'lar
{service=~".+"} |= "ERROR" | json | level="ERROR" | timestamp > now() - 5m
```

---

## Alerting

### Alert Kuralları

```yaml
# prometheus/alerts.yml
groups:
  - name: finance-ai-alerts
    rules:
      # Servis Uptime
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.instance }} down"
          description: "{{ $labels.job }} has been down for more than 1 minute"

      # High Error Rate
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate on {{ $labels.service }}"
          description: "Error rate is {{ $value | humanizePercentage }}"

      # High Latency
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High latency on {{ $labels.service }}"
          description: "p95 latency is {{ $value }}s"

      # Database Connections
      - alert: DatabaseConnectionWarning
        expr: db_pool_connections / db_pool_max_connections > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High database connection usage"
          description: "Connection usage is {{ $value | humanizePercentage }}"

      # No Decisions Made
      - alert: NoDecisionsMade
        expr: increase(active_decisions_total[1h]) == 0
        for: 2h
        labels:
          severity: warning
        annotations:
          summary: "No decisions made in the last hour"
          description: "Decision engine may be stuck"
```

### Alert Bildirimleri

| Alert | Severity | Bildirim |
|-------|----------|----------|
| ServiceDown | Critical | Slack + Email |
| HighErrorRate | Warning | Slack |
| HighLatency | Warning | Slack |
| DatabaseConnectionWarning | Warning | Email |
| NoDecisionsMade | Warning | Slack |

### Grafana Alert Yapılandırması

```json
{
  "name": "Finance AI Alerts",
  "rules": [
    {
      "name": "Service Health",
      "condition": "B",
      "data": [
        {
          "refId": "A",
          "queryType": "query",
          "relativeTimeRange": 300,
          "datasourceUid": "prometheus",
          "model": {
            "expr": "up",
            "refId": "A"
          }
        }
      ],
      "noDataState": "OK",
      "execErrState": "Error"
    }
  ]
}
```
