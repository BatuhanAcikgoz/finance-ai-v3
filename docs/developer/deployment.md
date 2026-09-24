# Deployment Rehberi

Finance AI V3'ün production ortamına deployment rehberi.

## 📋 İçindekiler

1. [Gereksinimler](#gereksinimler)
2. [Development Ortamı](#development-ortamı)
3. [Staging Ortamı](#staging-ortamı)
4. [Production Ortamı](#production-ortamı)
5. [Docker Deployment](#docker-deployment)
6. [Kubernetes Deployment](#kubernetes-deployment)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)

---

## Gereksinimler

### Minimum Gereksinimler

| Bileşen | CPU | RAM | Disk |
|---------|-----|-----|------|
| API Gateway | 2 core | 4 GB | 50 GB |
| Her Servis | 1 core | 1 GB | 10 GB |
| PostgreSQL | 4 core | 8 GB | 100 GB |
| Redis | 2 core | 4 GB | 20 GB |
| Qdrant | 2 core | 4 GB | 50 GB |

### Önerilen Gereksinimler

| Bileşen | CPU | RAM | Disk |
|---------|-----|-----|------|
| API Gateway | 4 core | 8 GB | 100 GB |
| Her Servis | 2 core | 2 GB | 20 GB |
| PostgreSQL | 8 core | 16 GB | 200 GB |
| Redis | 4 core | 8 GB | 50 GB |
| Qdrant | 4 core | 8 GB | 100 GB |

---

## Development Ortamı

### 1. Docker Servislerini Başlatma

```bash
cd infra/docker

# Tüm servisleri başlat
docker-compose up -d

# Servis durumlarını kontrol et
docker-compose ps
```

### 2. Python Bağımlılıkları

```bash
# uv ile senkronize et
uv sync --all-packages

# Geliştirme bağımlılıklarını yükle
uv sync --dev
```

### 3. Environment Dosyası

```bash
cp .env.example .env
# .env dosyasını düzenleyin
```

### 4. Veritabanı Migrasyonları

```bash
# Veritabanını başlat
psql -h localhost -U finance_ai_v3 -d finance_ai_v3 -f infra/docker/postgres/init.sql
```

### 5. Servisleri Başlatma

```bash
# API Gateway
cd apps/api-gateway && uvicorn src.main:app --reload --port 8000

# veya make komutu ile
make run
```

---

## Staging Ortamı

### Önkoşullar

- [ ] Staging sunucuları hazır
- [ ] Domain yapılandırıldı (staging.finance-ai-v3.com)
- [ ] SSL sertifikaları kuruldu
- [ ] Veritabanı hazır

### Adımlar

```bash
# 1. Staging branch'e geç
git checkout staging

# 2. En son kodu al
git pull origin staging

# 3. Environment dosyasını güncelle
# STAGING ortamı için yapılandırın

# 4. Docker Compose ile başlat
docker-compose -f docker-compose.staging.yml up -d

# 5. Health check
curl https://staging.finance-ai-v3.com/health
```

---

## Production Ortamı

### Önkoşullar

- [ ] Production sunucuları hazır
- [ ] Domain ve SSL yapılandırıldı
- [ ] Vault veya secrets manager kuruldu
- [ ] Backup stratejisi hazır
- [ ] Monitoring kuruldu

### Adımlar

```bash
# 1. Production branch'e geç
git checkout main

# 2. En son tag'e geç
git checkout tags/v0.1.0 -b release-0.1.0

# 3. Environment dosyasını production olarak yapılandır
# Kritik: Tüm API anahtarlarını ve şifreleri doğru girin

# 4. Production Docker Compose
docker-compose -f docker-compose.production.yml up -d

# 5. Health check
curl https://api.finance-ai-v3.com/health

# 6. Logları kontrol et
docker-compose logs -f api-gateway
```

---

## Docker Deployment

### docker-compose.yml

```yaml
# docker-compose.production.yml
version: '3.8'

services:
  api-gateway:
    build:
      context: ./apps/api-gateway
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
    env_file:
      - .env.production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  market_collector:
    build:
      context: ./services/market_collector
      dockerfile: Dockerfile
    env_file:
      - .env.production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  postgres:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### Dockerfile Örneği

```dockerfile
# apps/api-gateway/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Bağımlılıkları yükle
COPY pyproject.toml .
RUN pip install uv && uv sync --frozen

# Kodu kopyala
COPY src/ ./src/

# Environment değişkenleri
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Kubernetes Deployment

### Deployment YAML

```yaml
# k8s/api-gateway-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  labels:
    app: api-gateway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
        - name: api-gateway
          image: finance-ai-v3/api-gateway:latest
          ports:
            - containerPort: 8000
          env:
            - name: APP_ENV
              value: "production"
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: api-gateway-service
spec:
  selector:
    app: api-gateway
  ports:
    - port: 80
      targetPort: 8000
  type: LoadBalancer
```

### Helm Chart

```bash
# Helm ile deploy
helm install finance-ai-v3 ./charts/finance-ai-v3 \
  --set appEnv=production \
  --set image.tag=latest
```

---

## Monitoring

### Prometheus Metrikleri

Her servis aşağıdaki metrikleri expose eder:

| Metrik | Tip | Açıklama |
|--------|-----|----------|
| `http_requests_total` | Counter | Toplam HTTP istekleri |
| `http_request_duration_seconds` | Histogram | İstek süresi |
| `db_pool_connections` | Gauge | Veritabanı bağlantıları |
| `redis_commands_total` | Counter | Redis komutları |
| `active_decisions` | Gauge | Aktif kararlar |

### Grafana Dashboard

Dashboard ID: `finance-ai-v3-overview`

İçerdiği paneller:
- Request rate
- Error rate
- Latency percentiles
- Database connections
- Cache hit rate
- Active services health

---

## Troubleshooting

### Yaygın Hatalar

#### 1. "Connection refused" hatası

```bash
# Servislerin çalıştığını kontrol et
docker-compose ps

# Logları incele
docker-compose logs postgres
docker-compose logs redis
```

#### 2. "Database does not exist" hatası

```bash
# Veritabanını oluştur
psql -h localhost -U postgres -c "CREATE DATABASE finance_ai_v3;"

# init.sql çalıştır
psql -h localhost -U postgres -d finance_ai_v3 -f infra/docker/postgres/init.sql
```

#### 3. "Out of memory" hatası

```bash
# Docker memory ayarlarını kontrol et
docker stats

# Artıralım
# Docker Desktop -> Preferences -> Resources -> 8GB RAM
```

#### 4. "Port already in use" hatası

```bash
# Portu kullanan prosesi bul
lsof -i :8000

# Procesi sonlandır veya farklı port kullan
```

### Health Check Komutları

```bash
# API Gateway
curl http://localhost:8000/health

# PostgreSQL
docker-compose exec postgres pg_isready -U finance_ai_v3

# Redis
docker-compose exec redis redis-cli ping

# Qdrant
curl http://localhost:6333/health
```

### Log Analizi

```bash
# Tüm servislerin logları
docker-compose logs -f

# Belirli servis
docker-compose logs -f api-gateway

# Son 100 satır
docker-compose logs --tail=100 api-gateway

# Hata logları
docker-compose logs | grep -i error
```

---

## Backup ve Restore

### Veritabanı Backup

```bash
# Backup
docker-compose exec postgres pg_dump -U finance_ai_v3 > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20240115.sql | docker-compose exec -T postgres psql -U finance_ai_v3
```

### Redis Backup

```bash
# Redis dump
docker-compose exec redis redis-cli BGSAVE
docker-compose cp redis:/data/dump.rdb ./redis_backup.rdb
```

---

## Güvenlik Kontrol Listesi

- [ ] Tüm API anahtarları değiştirildi
- [ ] Güçlü şifreler kullanıldı
- [ ] SSL/TLS yapılandırıldı
- [ ] Firewall kuralları ayarlandı
- [ ] Rate limiting aktif
- [ ] Backup stratejisi test edildi
- [ ] Monitoring kuruldu
- [ ] Alertler yapılandırıldı
