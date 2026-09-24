# Docker Yapılandırması

Finance AI V3 Docker ve Docker Compose yapılandırması.

## 📋 İçindekiler

1. [Genel Bakış](#genel-bakış)
2. [Servisler](#servisler)
3. [Ağ Yapılandırması](#ağ-yapılandırması)
4. [Volume Yönetimi](#volume-yönetimi)
5. [Health Checks](#health-checks)

---

## Genel Bakış

```
infra/docker/
├── docker-compose.yml     # Ana Docker Compose dosyası
├── postgres/
│   └── init.sql          # Veritabanı başlatma scripti
├── litellm/
│   └── config.yaml        # LiteLLM yapılandırması
├── prometheus/
│   └── prometheus.yml     # Prometheus yapılandırması
├── grafana/
│   └── provisioning/      # Grafana provisioning
├── loki/
│   └── loki.yml          # Loki yapılandırması
└── otel/
    └── otel.yml          # OpenTelemetry Collector
```

---

## docker-compose.yml

```yaml
version: '3.8'

services:
  # === Database ===
  postgres:
    image: postgres:16-alpine
    container_name: finance-ai-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-finance_ai_v3}
      POSTGRES_USER: ${POSTGRES_USER:-finance_ai_v3}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-CHANGE_ME_IN_PRODUCTION}
      POSTGRES_MAX_CONNECTIONS: ${POSTGRES_MAX_CONNECTIONS:-20}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-finance_ai_v3} -d ${POSTGRES_DB:-finance_ai_v3}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - finance-ai-network

  # === Cache + Message Bus ===
  redis:
    image: redis:7-alpine
    container_name: finance-ai-redis
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - finance-ai-network

  # === Vector Store ===
  qdrant:
    image: qdrant/qdrant:v1.10.1
    container_name: finance-ai-qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"  # REST API
      - "6334:6334"  # gRPC API
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334
      QDRANT__SERVICE__HTTP_PORT: 6333
      QDRANT__CLUSTER__ENABLED: "false"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - finance-ai-network

  # === LLM Gateway ===
  litellm:
    image: ghcr.io/berriai/litellm:main
    container_name: finance-ai-litellm
    restart: unless-stopped
    ports:
      - "4000:4000"
    volumes:
      - ./litellm/config.yaml:/app/config.yaml:ro
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY:-CHANGE_ME_IN_PRODUCTION}
      STORE_MODEL_IN_DB: "true"
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - finance-ai-network

  # === Workflow Orchestration ===
  n8n:
    image: n8nio/n8n:latest
    container_name: finance-ai-n8n
    restart: unless-stopped
    ports:
      - "5678:5678"
    volumes:
      - n8n_data:/home/node/.n8n
      - ./n8n/workflows:/workflows:ro
    environment:
      N8N_BASIC_AUTH_ACTIVE: "true"
      N8N_BASIC_AUTH_USER: admin
      N8N_BASIC_AUTH_PASSWORD: ${N8N_PASSWORD:-CHANGE_ME_IN_PRODUCTION}
      WEBHOOK_URL: ${WEBHOOK_URL:-http://localhost:5678}
      DB_POSTGRESDB_HOST: postgres
      DB_POSTGRESDB_PORT: 5432
      DB_POSTGRESDB_DATABASE: ${POSTGRES_DB:-finance_ai_v3}
      DB_POSTGRESDB_USER: ${POSTGRES_USER:-finance_ai_v3}
      DB_POSTGRESDB_PASSWORD: ${POSTGRES_PASSWORD:-CHANGE_ME_IN_PRODUCTION}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - finance-ai-network

  # === Observability ===
  prometheus:
    image: prom/prometheus:latest
    container_name: finance-ai-prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    networks:
      - finance-ai-network

  grafana:
    image: grafana/grafana:latest
    container_name: finance-ai-grafana
    restart: unless-stopped
    ports:
      - "3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-CHANGE_ME_IN_PRODUCTION}
    depends_on:
      - prometheus
    networks:
      - finance-ai-network

  loki:
    image: grafana/loki:latest
    container_name: finance-ai-loki
    restart: unless-stopped
    ports:
      - "3100:3100"
    volumes:
      - loki_data:/loki
      - ./loki/loki.yml:/etc/loki/local-config.yaml:ro
    command: -config.file=/etc/loki/local-config.yaml
    networks:
      - finance-ai-network

  jaeger:
    image: jaegertracing/all-in-one:latest
    container_name: finance-ai-jaeger
    restart: unless-stopped
    ports:
      - "16686:16686"  # UI
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
    environment:
      COLLECTOR_OTLP_ENABLED: "true"
    networks:
      - finance-ai-network

  otel-collector:
    image: otel/opentelemetry-collector:latest
    container_name: finance-ai-otel
    restart: unless-stopped
    ports:
      - "4317:4317"   # OTLP gRPC receiver
      - "4318:4318"   # OTLP HTTP receiver
      - "8888:8888"   # Prometheus exporter metrics
    volumes:
      - ./otel/otel.yml:/etc/otelcol/config.yaml:ro
    command: ["--config=/etc/otelcol/config.yaml"]
    networks:
      - finance-ai-network

# =============================================================================
# Volumes
# =============================================================================
volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  qdrant_data:
    driver: local
  n8n_data:
    driver: local
  prometheus_data:
    driver: local
  grafana_data:
    driver: local
  loki_data:
    driver: local

# =============================================================================
# Networks
# =============================================================================
networks:
  finance-ai-network:
    driver: bridge
    name: finance-ai-network
```

---

## Servisler

### PostgreSQL

- **Port**: 5432
- **Kullanıcı**: finance_ai_v3
- **Veritabanı**: finance_ai_v3
- **Init Script**: `postgres/init.sql`

### Redis

- **Port**: 6379
- **Persistence**: AOF (Append Only File)
- **Max Memory**: 512MB
- **Eviction Policy**: allkeys-lru

### Qdrant

- **REST API Port**: 6333
- **gRPC Port**: 6334
- **Persistence**: Disk tabanlı

### LiteLLM

- **Port**: 4000
- **Config**: `litellm/config.yaml`
- **Master Key**: LITELLM_MASTER_KEY

### n8n

- **Port**: 5678
- **Basic Auth**: Aktif
- **Database**: PostgreSQL

---

## Ağ Yapılandırması

Tüm servisler `finance-ai-network` bridge network'ünde çalışır.

### Port Eşleştirmeleri

| Servis | Container Port | Host Port |
|--------|---------------|-----------|
| postgres | 5432 | 5432 |
| redis | 6379 | 6379 |
| qdrant | 6333 | 6333 |
| qdrant (gRPC) | 6334 | 6334 |
| litellm | 4000 | 4000 |
| n8n | 5678 | 5678 |
| prometheus | 9090 | 9090 |
| grafana | 3000 | 3001 |
| loki | 3100 | 3100 |
| jaeger | 16686 | 16686 |

---

## Volume Yönetimi

### Volume Listesi

```bash
# Volume'ları listele
docker volume ls | grep finance

# Volume'ları temizle (Dikkatli kullanın!)
docker volume rm finance-ai-postgres_data
docker volume rm finance-ai-redis_data
```

### Volume Backup

```bash
# PostgreSQL backup
docker run --rm \
  -v finance-ai-postgres_data:/data \
  -v $(pwd):/backup \
  postgres:16-alpine \
  tar czf /backup/postgres_backup.tar.gz /data

# Redis backup
docker exec finance-ai-redis redis-cli BGSAVE
docker cp finance-ai-redis:/data/dump.rdb ./redis_backup.rdb
```

---

## Health Checks

### Servis Health Check Komutları

```bash
# PostgreSQL
docker exec finance-ai-postgres pg_isready -U finance_ai_v3

# Redis
docker exec finance-ai-redis redis-cli ping

# Qdrant
curl -f http://localhost:6333/health

# LiteLLM
curl -f http://localhost:4000/health

# n8n
curl -f http://localhost:5678/healthz
```

---

## Log Yönetimi

### Container Loglarını Görüntüleme

```bash
# Tüm loglar
docker-compose logs -f

# Belirli servis
docker-compose logs -f postgres

# Son 100 satır
docker-compose logs --tail=100 redis
```

### Log Rotasyonu

```yaml
# docker-compose.yml'de
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```
