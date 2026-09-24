# Finance AI V3 - Technical Documentation

> Türk Sermaye Piyasaları için Otonom Finansal Araştırma Analisti

Finance AI V3, Borsa İstanbul (BIST) için geliştirilmiş kapsamlı bir finansal otomasyon platformudur. Piyasa verilerini toplayan, teknik ve temel analiz yapan, karar mekanizmalarını çalıştıran ve yatırım portföylerini yöneten mikroservis tabanlı bir mimari üzerine inşa edilmiştir.

## 📚 Dokümantasyon Yapısı

```
docs/
├── README.md                      # Bu dosya - Proje dokümantasyonuna genel bakış
├── index.md                       # Başlangıç rehberi
│
├── # ─────────────────────────────────────────────────────────────────
│   # KULLANICI KILAVUZLARI
│   # ─────────────────────────────────────────────────────────────────
│
├── user/
│   ├── README.md                  # Kullanıcı dokümantasyonu ana sayfası
│   ├── getting-started.md         # Başlangıç rehberi
│   ├── portfolio-management.md     # Portföy yönetimi
│   ├── decision-system.md         # Karar sistemi
│   ├── notifications.md          # Bildirim sistemi
│   └── faq.md                    # Sıkça sorulan sorular
│
├── # ─────────────────────────────────────────────────────────────────
│   # GELİŞTİRİCİ KILAVUZLARI
│   # ─────────────────────────────────────────────────────────────────
│
├── developer/
│   ├── README.md                  # Geliştirici ana rehberi
│   ├── architecture.md           # Sistem mimarisi
│   ├── services.md               # Tüm servislerin detaylı açıklaması
│   ├── database.md               # Veritabanı şemaları
│   ├── api-reference.md          # API referansı
│   ├── configuration.md           # Konfigürasyon rehberi
│   ├── testing.md                # Test stratejisi
│   └── deployment.md             # Deployment rehberi
│
├── # ─────────────────────────────────────────────────────────────────
│   # TEKNİK REFERANSLAR
│   # ─────────────────────────────────────────────────────────────────
│
├── reference/
│   ├── api/
│   │   ├── README.md             # API genel bakış
│   │   ├── endpoints.md          # Endpoint referansı
│   │   ├── authentication.md     # Kimlik doğrulama
│   │   └── schemas.md            # Veri şemaları
│   │
│   ├── services/
│   │   ├── market-collector.md   # Piyasa verisi toplayıcı
│   │   ├── kap-collector.md      # KAP açıklamaları
│   │   ├── news-collector.md     # Haber toplayıcı
│   │   ├── technical-analysis.md  # Teknik analiz
│   │   ├── fundamental-analysis.md# Temel analiz
│   │   ├── decision-engine.md    # Karar motoru
│   │   ├── compliance-agent.md   # Uyumluluk ajanı
│   │   ├── portfolio-engine.md    # Portföy motoru
│   │   ├── risk-engine.md        # Risk motoru
│   │   └── memory-agent.md       # Bellek ajanı
│   │
│   └── infrastructure/
│       ├── docker.md             # Docker yapılandırması
│       ├── monitoring.md         # İzleme ve alerting
│       └── logging.md            # Loglama stratejisi
│
└── # ─────────────────────────────────────────────────────────────────
    # PROJE METADATASI
    # ─────────────────────────────────────────────────────────────────

## 🎯 Proje Özellikleri

### Veri Toplama Servisleri
- **Market Collector**: BIST Gerçek zamanlı piyasa verileri (tick, bar, endeks)
- **KAP Collector**: KAP kamu açıklamaları ve mali raporlar
- **News Collector**: Finans haberleri ve RSS kaynakları
- **Macro Collector**: TCMB, TÜİK, BDDK makroekonomik verileri
- **TEFAS Collector**: Yatırım fonları verileri

### Analiz Servisleri
- **Technical Analysis**: 20+ teknik gösterge (RSI, MACD, Bollinger, vb.)
- **Fundamental Analysis**: KAP açıklamalarından mali oran çıkarımı
- **Sentiment Analysis**: Haber ve açıklama duygu analizi
- **Sector Analysis**: Sektör karşılaştırmalı analiz
- **Macro Analysis**: Makroekonomik göstergelerin portföy etkisi

### Karar ve Portföy Servisleri
- **Decision Engine**: Çoklu kanıt birleştirme ve trading kararları
- **Portfolio Engine**: Portföy takibi ve rebalancing
- **Risk Engine**: VaR, CVaR, konsantrasyon riski hesaplamaları
- **Compliance Agent**: Kararların yasal uyumluluk kontrolü

### Destek Servisleri
- **Memory Agent**: Qdrant vektör veritabanı ile benzerlik araması
- **Backtest Agent**: Strateji geriye dönük test
- **Notification Dispatch**: E-posta ve bildirim gönderimi
- **Report Generator**: Analiz ve karar raporları

## 🏗️ Teknoloji Stack

| Katman | Teknoloji |
|--------|-----------|
| **Veritabanı** | PostgreSQL 16, Redis 7, Qdrant 1.10 |
| **Programlama** | Python 3.11+, async/await |
| **LLM Gateway** | LiteLLM (OpenAI, Anthropic, MiniMax) |
| **Workflow** | n8n |
| **Container** | Docker, Docker Compose |
| **İzleme** | Prometheus, Grafana, Jaeger, Loki |
| **API Gateway** | FastAPI tabanlı |

## 🚀 Hızlı Başlangıç

### Gereksinimler
- Docker ve Docker Compose
- Python 3.11+
- PostgreSQL, Redis, Qdrant

### Kurulum

```bash
# 1. Repoyu klonlayın
git clone https://github.com/your-org/FinanceAutomations.git
cd FinanceAutomations

# 2. Environment dosyasını kopyalayın
cp .env.example .env

# 3. .env dosyasını düzenleyin (API anahtarlarınızı girin)

# 4. Docker servislerini başlatın
docker-compose -f infra/docker/docker-compose.yml up -d

# 5. Python bağımlılıklarını yükleyin
uv sync

# 6. Servisleri başlatın
make run
```

Detaylı kurulum için [Kurulum Rehberi](developer/deployment.md) sayfasını ziyaret edin.

## 📊 Sistem Mimarisi

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Gateway                              │
│                    (FastAPI + JWT Auth)                          │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐       ┌───────────────┐
│   Collectors  │      │   Analyzers   │       │   Engines     │
├───────────────┤      ├───────────────┤       ├───────────────┤
│ Market        │      │ Technical     │       │ Decision      │
│ KAP           │      │ Fundamental   │       │ Portfolio     │
│ News          │      │ Sentiment     │       │ Risk          │
│ Macro         │      │ Sector        │       │ Compliance    │
│ TEFAS         │      │               │       │ Backtest      │
└───────────────┘      └───────────────┘       └───────────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                ▼
                    ┌─────────────────────┐
                    │   Shared Services   │
                    ├─────────────────────┤
                    │ PostgreSQL          │
                    │ Redis               │
                    │ Qdrant              │
                    │ LiteLLM             │
                    └─────────────────────┘
```

## 📖 Dokümantasyon Bölümleri

### Kullanıcılar İçin
- [Başlangıç Rehberi](user/getting-started.md) - Sistemi hızlıca tanıyın
- [Portföy Yönetimi](user/portfolio-management.md) - Portföy oluşturma ve yönetme
- [Karar Sistemi](user/decision-system.md) - Trading kararlarının nasıl alındığını anlayın
- [Bildirimler](user/notifications.md) - Alert ve notification yapılandırması

### Geliştiriciler İçin
- [Mimari](developer/architecture.md) - Detaylı sistem mimarisi
- [Servisler](developer/services.md) - Tüm servislerin açıklaması
- [Veritabanı](developer/database.md) - Şema ve tablo yapıları
- [API Referansı](developer/api-reference.md) - Tüm API endpointleri
- [Konfigürasyon](developer/configuration.md) - Environment değişkenleri
- [Test](developer/testing.md) - Test stratejisi
- [Deployment](developer/deployment.md) - Production deployment

## 🔒 Güvenlik

- Tüm API'ler JWT ile korunmaktadır
- Hassas veriler (API anahtarları, şifreler) environment variable olarak saklanır
- Veritabanı bağlantıları SSL/TLS ile şifrelenebilir
- Rate limiting uygulanmaktadır

## 📝 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## 🤝 Katkıda Bulunma

Katkıda bulunmak için lütfen CONTRIBUTING.md dosyasını inceleyin.

---

**Finance AI V3** - Türk Sermaye Piyasaları için Otonom Finansal Araştırma Analisti
