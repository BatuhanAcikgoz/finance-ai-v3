# Konfigürasyon

Finance AI V3'ün environment değişkenleri ve konfigürasyon ayarları.

## 📋 İçindekiler

1. [Environment Dosyası](#environment-dosyası)
2. [Uygulama Ayarları](#uygulama-ayarları)
3. [Veritabanı Ayarları](#veritabanı-ayarları)
4. [Redis Ayarları](#redis-ayarları)
5. [LLM Ayarları](#llm-ayarları)
6. [Veri Kaynakları](#veri-kaynakları)
7. [Güvenlik Ayarları](#güvenlik-ayarları)
8. [İzleme Ayarları](#izleme-ayarları)

---

## Environment Dosyası

`.env.example` dosyasını `.env` olarak kopyalayın:

```bash
cp .env.example .env
```

**Önemli**: `.env` dosyasını **asla** versiyon kontrolüne commitlemeyin!

---

## Uygulama Ayarları

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `APP_ENV` | Ortam (development, staging, production) | development |
| `APP_NAME` | Uygulama adı | finance-ai-v3 |
| `APP_VERSION` | Versiyon | 0.1.0 |

---

## Veritabanı Ayarları

### PostgreSQL

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `POSTGRES_HOST` | PostgreSQL host | localhost |
| `POSTGRES_PORT` | PostgreSQL port | 5432 |
| `POSTGRES_DB` | Veritabanı adı | finance_ai_v3 |
| `POSTGRES_USER` | Kullanıcı adı | finance_ai_v3 |
| `POSTGRES_PASSWORD` | Şifre | **Zorunlu** |
| `POSTGRES_MAX_CONNECTIONS` | Maks. bağlantı | 20 |

```bash
POSTGRES_PASSWORD=CHANGE_ME_IN_PRODUCTION
```

---

## Redis Ayarları

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `REDIS_HOST` | Redis host | localhost |
| `REDIS_PORT` | Redis port | 6379 |
| `REDIS_PASSWORD` | Şifre | - |
| `REDIS_DB` | Veritabanı numarası | 0 |
| `REDIS_CLUSTER_ENABLED` | Cluster modu | false |

---

## Qdrant Ayarları

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `QDRANT_HOST` | Qdrant host | localhost |
| `QDRANT_PORT` | REST API port | 6333 |
| `QDRANT_GRPC_PORT` | gRPC port | 6334 |
| `QDRANT_API_KEY` | API anahtarı | - |
| `QDRANT_COLLECTION_PREFIX` | Koleksiyon ön eki | finance_ai_v3 |

---

## LLM Ayarları

### LiteLLM Gateway

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `LITELLM_HOST` | LiteLLM host | localhost |
| `LITELLM_PORT` | LiteLLM port | 4000 |
| `LITELLM_MASTER_KEY` | Master anahtar | **Zorunlu** |

### Sağlayıcı Ayarları

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `LITELLM_PROVIDER` | Birincil sağlayıcı | openai |
| `OPENAI_API_KEY` | OpenAI API anahtarı | **Zorunlu** |
| `OPENAI_BASE_URL` | OpenAI base URL | https://api.openai.com/v1 |
| `OPENAI_MODEL` | Model | gpt-4o |

### Yedek Sağlayıcılar

| Değişken | Açıklama |
|----------|----------|
| `ANTHROPIC_API_KEY` | Anthropic API anahtarı |
| `MINIMAX_API_KEY` | MiniMax API anahtarı |
| `MINIMAX_BASE_URL` | MiniMax base URL |

### Maliyet Limitleri

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `LITELLM_MAX_MONTHLY_COST` | Aylık maks. maliyet (USD) | 500 |
| `LITELLM_COST_PER_RECOMMENDATION` | Öneri başına maks. maliyet | 0.50 |

---

## Veri Kaynakları

### BIST

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `BIST_API_KEY` | BIST API anahtarı | **Zorunlu** |
| `BIST_API_BASE_URL` | BIST API URL | https://api.bist.com.tr/v1 |
| `BIST_WS_URL` | WebSocket URL | wss://ws.bist.com.tr |

### KAP

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `KAP_API_KEY` | KAP API anahtarı | **Zorunlu** |
| `KAP_API_BASE_URL` | KAP API URL | https://api.kap.org.tr/v1 |
| `KAP_POLL_INTERVAL_SECONDS` | Anket aralığı | 300 |

### TEFAS

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `TEFAS_SCRAPE_BASE_URL` | TEFAS URL | https://www.tefas.com.tr |

### Haberler

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `NEWS_RSS_FEEDS` | RSS feed URL'leri (virgülle ayrılmış) | - |
| `NEWS_POLL_INTERVAL_SECONDS` | Anket aralığı | 120 |

### TCMB

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `TCMB_EVDS_API_KEY` | TCMB EVDS API anahtarı | **Zorunlu** |
| `TCMB_EVDS_BASE_URL` | TCMB EVDS URL | https://evds2.tcmb.gov.tr/service |

### TÜİK

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `TUIK_API_KEY` | TÜİK API anahtarı | **Zorunlu** |
| `TUIK_BASE_URL` | TÜİK API URL | https://api.tuik.gov.tr |

### BDDK

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `BDDK_BULLETIN_URL` | BDDK bülten URL | https://www.bddk.org.tr |

---

## E-posta Ayarları

### SendGrid

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `SENDGRID_API_KEY` | SendGrid API anahtarı | - |
| `SENDGRID_FROM_EMAIL` | Gönderen e-posta | noreply@finance-ai.local |
| `SENDGRID_FROM_NAME` | Gönderen adı | Finance AI V3 |

### SMTP Yedek

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `SMTP_HOST` | SMTP host | localhost |
| `SMTP_PORT` | SMTP port | 1025 |
| `SMTP_USER` | SMTP kullanıcı | - |
| `SMTP_PASSWORD` | SMTP şifre | - |
| `SMTP_USE_TLS` | TLS kullan | false |

---

## Güvenlik Ayarları

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `SECRET_KEY` | Uygulama gizli anahtarı (min 32 karakter) | **Zorunlu** |
| `JWT_SECRET_KEY` | JWT imzalama anahtarı (min 32 karakter) | **Zorunlu** |
| `JWT_ALGORITHM` | JWT algoritması | HS256 |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Token süresi (dakika) | 1440 (24 saat) |
| `API_RATE_LIMIT_PER_MINUTE` | Genel rate limit | 100/dakika |
| `API_RATE_LIMIT_AUTH_PER_MINUTE` | Auth rate limit | 10/dakika |

---

## İzleme Ayarları

### OpenTelemetry

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint | http://localhost:4317 |
| `OTEL_SERVICE_NAME` | Servis adı | finance-ai-v3 |
| `OTEL_TRACES_SAMPLER` | Trace örnekleyici | parentbased_traceidratio |
| `OTEL_TRACES_SAMPLER_ARG` | Örnekleyici argümanı | 0.1 |

### Prometheus

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `PROMETHEUS_PORT` | Prometheus port | 9090 |

### Jaeger

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `JAEGER_AGENT_HOST` | Jaeger agent host | localhost |
| `JAEGER_AGENT_PORT` | Jaeger agent port | 6831 |

---

## Özellik Bayrakları

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `FEATURE_BACKTEST_ENABLED` | Backtest özelliği | true |
| `FEATURE_MULTI_PORTFOLIO_ENABLED` | Çoklu portföy | false |
| `FEATURE_REAL_TIME_NEWS_ENABLED` | Gerçek zamanlı haberler | true |

---

## Örnek .env Dosyası

```bash
# =============================================================================
# Application
# =============================================================================
APP_ENV=development
APP_NAME=finance-ai-v3
APP_VERSION=0.1.0

# =============================================================================
# Database - PostgreSQL 16
# =============================================================================
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=finance_ai_v3
POSTGRES_USER=finance_ai_v3
POSTGRES_PASSWORD=CHANGE_ME_IN_PRODUCTION
POSTGRES_MAX_CONNECTIONS=20

# =============================================================================
# Cache + Message Bus - Redis 7
# =============================================================================
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=CHANGE_ME_IN_PRODUCTION
REDIS_DB=0

# =============================================================================
# Vector Store - Qdrant 1.10
# =============================================================================
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=CHANGE_ME_IN_PRODUCTION

# =============================================================================
# LLM Gateway - LiteLLM
# =============================================================================
LITELLM_HOST=localhost
LITELLM_PORT=4000
LITELLM_MASTER_KEY=CHANGE_ME_IN_PRODUCTION
OPENAI_API_KEY=CHANGE_ME_IN_PRODUCTION
OPENAI_MODEL=gpt-4o

# =============================================================================
# Security
# =============================================================================
SECRET_KEY=CHANGE_ME_32_CHARS_MINIMUM_SECRET_KEY
JWT_SECRET_KEY=CHANGE_ME_32_CHARS_MINIMUM_JWT_SECRET
```

---

## Production Notları

### Güvenlik Kontrol Listesi

- [ ] Tüm `CHANGE_ME` değerlerini değiştirin
- [ ] `SECRET_KEY` ve `JWT_SECRET_KEY` için güvenli rastgele değerler kullanın
- [ ] API anahtarlarını güvenli bir şekilde saklayın (Vault, AWS Secrets Manager)
- [ ] TLS/SSL sertifikalarını yapılandırın
- [ ] Rate limit değerlerini production'a uygun ayarlayın
