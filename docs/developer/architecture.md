# Sistem Mimarisi

Finance AI V3, mikroservis mimarisi üzerine inşa edilmiş, Türk sermaye piyasaları için tasarlanmış bir finansal otomasyon platformudur.

## 📋 İçindekiler

1. [Mimari Genel Bakış](#mimari-genel-bakış)
2. [Servis Katmanları](#servis-katmanları)
3. [Veri Akışı](#veri-akışı)
4. [İletişim Deseni](#iletişim-deseni)
5. [Veritabanı Mimarisi](#veritabanı-mimarisi)

---

## Mimari Genel Bakış

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENTS                                   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │ Web App │  │Mobile   │  │  n8n    │  │  API    │            │
│  │Dashboard│  │ App     │  │Workflows│  │ Clients │            │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘            │
└───────┼────────────┼────────────┼────────────┼──────────────────┘
        │            │            │            │
        └────────────┴────────────┴────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API GATEWAY                                 │
│                  (FastAPI + JWT Auth)                            │
│         Rate Limiting │ Authentication │ Routing                │
└─────────────────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  COLLECTORS  │ │   ANALYZERS  │ │    ENGINES    │
│               │ │              │ │               │
│ Market        │ │ Technical    │ │ Decision      │
│ KAP           │ │ Fundamental  │ │ Portfolio     │
│ News          │ │ Sentiment    │ │ Risk          │
│ Macro         │ │ Sector       │ │ Compliance    │
│ TEFAS         │ │              │ │ Backtest      │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                │                │
        └────────────────┴────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SHARED SERVICES                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │PostgreSQL│  │  Redis   │  │  Qdrant  │  │ LiteLLM  │        │
│  │  (Data)  │  │(Cache/   │  │ (Vector  │  │ (LLM     │        │
│  │          │  │  PubSub) │  │  Store)  │  │ Gateway) │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │Prometheus│  │ Grafana  │  │  Jaeger  │  │   Loki   │        │
│  │Metrics   │  │Dashboards│  │ Tracing  │  │  Logs    │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Servis Katmanları

### 1. Toplama Servisleri (Collectors)

Veri kaynaklarından veri toplayan servislerdir.

| Servis | Veri Kaynağı | Frekans |
|--------|---------------|---------|
| `market_collector` | BIST API | 10 saniye (piyasa açıkken) |
| `kap_collector` | KAP API | 5 dakika |
| `news_collector` | RSS Feed | 2 dakika |
| `macro_collector` | TCMB/TÜİK/BDDK | 1 saat |
| `tefas_collector` | TEFAS | 1 saat |

### 2. Analiz Servisleri (Analyzers)

Toplanan verileri işleyen ve içgörü üreten servislerdir.

| Servis | Girdi | Çıktı |
|--------|-------|-------|
| `technical_analysis` | OHLCV verisi | 20+ teknik gösterge |
| `fundamental_analysis` | KAP açıklamaları | Mali oranlar |
| `sentiment_analysis` | Haber metinleri | Duygu skoru |
| `sector_analysis` | Sektör verileri | Sektör sinyalleri |
| `macro_analysis` | Makro veriler | Makro sinyaller |

### 3. Motor Servisleri (Engines)

Karar ve portföy yönetimi yapan servislerdir.

| Servis | Sorumluluk |
|--------|------------|
| `decision_engine` | Kanıt birleştirme ve karar üretimi |
| `portfolio_engine` | Portföy takibi ve işlem yönetimi |
| `risk_engine` | Risk hesaplamaları |
| `compliance_agent` | Uyumluluk kontrolü |
| `backtest_agent` | Strateji geriye dönük test |
| `memory_agent` | Vektör araması ve embedding |

---

## Veri Akışı

### Piyasa Verisi Akışı

```
BIST API
    │
    ▼
market_collector
    │
    ├──► PostgreSQL (market_data.ticks, market_data.bars)
    │
    ├──► Redis (cache: tick:{ticker}:latest)
    │
    └──► Redis PubSub (raw.market.tick)
            │
            ▼
        technical_analysis
            │
            ├──► PostgreSQL (analysis.technical_indicators)
            │
            └──► Redis PubSub (analysis.technical.signal)
                    │
                    ▼
                decision_engine
```

### KAP Açıklama Akışı

```
KAP API
    │
    ▼
kap_collector
    │
    ├──► PostgreSQL (kap.disclosures)
    │
    ├──► Qdrant (embedding)
    │
    └──► Redis PubSub (raw.kap.material)
            │
            ▼
        fundamental_analysis
            │
            ├──► PostgreSQL (analysis.fundamental_analyses)
            │
            └──► Redis PubSub (analysis.fundamental.complete)
```

### Karar Akışı

```
decision_engine
    │
    ├──► Mevcut analizleri çek (PostgreSQL)
    │
    ├──► Kanıtları ağırlıklandır
    │
    ├──► Güven skoru hesapla
    │
    ├──► Karar üret (BUY/SELL/HOLD)
    │
    ├──► PostgreSQL (decision.decisions)
    │
    └──► Redis PubSub (decision.pending_compliance)
            │
            ▼
        compliance_agent
            │
            ├──► Yasaklı dil kontrolü
            │
            ├──► Feragatname kontrolü
            │
            ├──► Pozisyon limit kontrolü
            │
            ├──► PostgreSQL (audit.compliance_audits)
            │
            └──► Redis PubSub (compliance.approved/Blocked)
                    │
                    ▼
                notification_dispatch
                    │
                    ▼
                E-posta / Push Bildirim
```

---

## İletişim Deseni

### Senkron (HTTP/REST)

Client'lar ve API Gateway arasında:

```
Client  ──HTTP──►  API Gateway  ──HTTP──►  Service
```

### Asenkron (Redis PubSub)

Servisler arasında olay gönderimi:

```
Service A  ──publish──►  Redis Channel  ──subscribe──►  Service B
```

### Event Tipleri

| Kanal | Olay | Üreten | Tüketen |
|-------|------|--------|---------|
| `raw.market.tick` | Anlık fiyat | market_collector | technical_analysis |
| `raw.kap.material` | KAP açıklaması | kap_collector | fundamental_analysis |
| `raw.news.article` | Haber | news_collector | sentiment_analysis |
| `analysis.technical.signal` | Teknik sinyal | technical_analysis | decision_engine |
| `analysis.fundamental.complete` | Temel analiz | fundamental_analysis | decision_engine |
| `decision.pending_compliance` | Karar beklemede | decision_engine | compliance_agent |
| `compliance.approved` | Karar onaylandı | compliance_agent | notification_dispatch |
| `trade.executed` | İşlem gerçekleşti | portfolio_engine | - |

---

## Veritabanı Mimarisi

### Schema Organizasyonu

```
finance_ai_v3
├── market_data      # Piyasa verileri
│   ├── ticks        # Anlık fiyatlar
│   ├── bars         # OHLCV barlar
│   ├── index_values # Endeks değerleri
│   └── tickers      # Hisse senedi listesi
├── kap              # KAP açıklamaları
├── news             # Haberler
├── tefas            # Yatırım fonları
├── macro            # Makroekonomik veriler
├── analysis         # Analiz sonuçları
│   ├── technical_indicators
│   ├── technical_signals
│   ├── fundamental_analyses
│   ├── sentiment_analyses
│   └── sector_analyses
├── portfolio        # Portföyler ve pozisyonlar
│   ├── portfolios
│   └── holdings
├── decision         # Kararlar
├── risk             # Risk değerlendirmeleri
├── notification     # Bildirimler
├── audit            # Denetim kayıtları
└── backtest         # Geriye dönük testler
```

### Veritabanı Bağlantı Havuzları

Her servis, veritabanına kendi connection pool'u üzerinden erişir:

```python
# Shared database connection
from shared.db import get_db_pool

pool = get_db_pool()
async with pool.connection() as conn:
    result = await conn.fetch("SELECT * FROM market_data.tickers")
```

### Redis Kullanımı

| Kullanım | Tip | Örnek |
|----------|-----|-------|
| Cache | Key-Value | `tick:THYAO:latest` |
| Pub/Sub | Event | `raw.market.tick` |
| Idempotency | Key-Value | `idempotency:{key}` |
| Rate Limiting | Key-Value | `rate_limit:user:{id}` |

### Qdrant (Vektör Veritabanı)

| Koleksiyon | Amaç |
|------------|------|
| `news` | Haber metinleri embedding |
| `kap` | KAP açıklamaları embedding |
| `decision` | Karar metinleri embedding |
| `analysis` | Analiz sonuçları embedding |

---

## Güvenlik Mimarisi

```
┌─────────────────────────────────────────────────────────────────┐
│                      GÜVENLİK KATMANLARI                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   TLS/SSL   │    │  JWT Auth   │    │ Rate Limit  │         │
│  │  Transport  │    │   Token     │    │   100/min   │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  API Key   │    │  Input Val  │    │ SQL Inj.    │         │
│  │ Validation │    │   ation     │    │  Prevention │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Ölçeklenebilirlik

### Yatay Ölçeklenme

Her mikroservis bağımsız olarak ölçeklenebilir:

```
                    ┌─────────────┐
                    │ Load Balancer│
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
   ┌───────────┐     ┌───────────┐     ┌───────────┐
   │Instance 1 │     │Instance 2 │     │Instance 3 │
   │(market_   │     │(market_   │     │(market_   │
   │collector) │     │collector) │     │collector) │
   └───────────┘     └───────────┘     └───────────┘
```

### Kubernetes Desteği (Gelecek)

Sistem, Kubernetes üzerinde çalışacak şekilde tasarlanmıştır:
- Otomatik ölçeklendirme (HPA)
- Rolling update
- Health check endpoints
- Graceful shutdown

---

## Sonraki Adımlar

- [Servis Detayları](services.md) - Her servisin detaylı açıklaması
- [Veritabanı](database.md) - Tablo şemaları ve indeksler
- [Konfigürasyon](configuration.md) - Environment değişkenleri
