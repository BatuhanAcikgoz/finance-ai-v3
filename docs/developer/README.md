# Geliştirici Dokümantasyonu

Bu klasör, Finance AI V3 projesini **geliştirici** olarak nasıl katkıda bulunacağınızı ve sistemin nasıl çalıştığını açıklar.

## 📋 İçindekiler

### Başlangıç
- [Mimari](architecture.md) - Sistem mimarisi ve bileşenler
- [Servisler](services.md) - Tüm servislerin detaylı açıklaması
- [Veritabanı](database.md) - PostgreSQL şemaları ve tablolar
- [Konfigürasyon](configuration.md) - Environment değişkenleri

### Geliştirme
- [API Referansı](api-reference.md) - Tüm API endpointleri
- [Testing](testing.md) - Test stratejisi ve yazımı
- [Deployment](deployment.md) - Production deployment

### Alt Yapı
- [Docker](../reference/infrastructure/docker.md) - Container yapılandırması
- [Monitoring](../reference/infrastructure/monitoring.md) - İzleme ve alerting
- [Logging](../reference/infrastructure/logging.md) - Loglama stratejisi

## 🏗️ Mimariye Genel Bakış

Finance AI V3, mikroservis mimarisi kullanır:

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
                    │ Redis              │
                    │ Qdrant             │
                    │ LiteLLM            │
                    └─────────────────────┘
```

## 🔧 Geliştirme Ortamı

### Gereksinimler

- Python 3.11+
- Docker ve Docker Compose
- PostgreSQL 16
- Redis 7
- Qdrant 1.10

### Hızlı Kurulum

```bash
# 1. Environment dosyasını kopyalayın
cp .env.example .env

# 2. Docker servislerini başlatın
docker-compose -f infra/docker/docker-compose.yml up -d

# 3. Python bağımlılıklarını yükleyin
uv sync

# 4. Servisleri başlatın
make run
```

## 📁 Proje Yapısı

```
FinanceAutomations/
├── apps/
│   └── api-gateway/           # FastAPI API Gateway
├── services/
│   ├── collector/            # Veri toplayıcılar
│   │   ├── market_collector/
│   │   ├── kap_collector/
│   │   ├── news_collector/
│   │   ├── macro_collector/
│   │   └── tefas_collector/
│   ├── analysis/              # Analiz servisleri
│   │   ├── technical_analysis/
│   │   ├── fundamental_analysis/
│   │   ├── sentiment_analysis/
│   │   └── sector_analysis/
│   ├── engine/                # Motor servisleri
│   │   ├── decision_engine/
│   │   ├── portfolio_engine/
│   │   └── risk_engine/
│   └── agent/                 # Agent servisleri
│       ├── compliance_agent/
│       ├── backtest_agent/
│       └── memory_agent/
├── shared/                    # Paylaşılan kodlar
│   └── src/shared/
│       ├── db/               # Veritabanı bağlantısı
│       ├── redis/            # Redis client
│       └── calendar/         # BIST takvimi
├── infra/
│   └── docker/               # Docker Compose
├── workflows/                 # n8n workflow'ları
├── schemas/                   # JSON şemaları
└── tests/                    # Testler
```

## 🚀 Yeni Servis Ekleme

### 1. Servis Şablonu

Her servis aşağıdaki yapıyı takip eder:

```
services/
└── my_service/
    ├── pyproject.toml
    └── src/
        └── my_service/
            ├── __init__.py
            ├── config.py      # Pydantic settings
            ├── models.py       # Pydantic modelleri
            ├── service.py      # Ana iş mantığı
            └── handlers.py     # API endpoint'leri
```

### 2. pyproject.toml

```toml
[project]
name = "my_service"
version = "0.1.0"

[tool.uv]
workspace = ["."]
```

### 3. Konfigürasyon

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://localhost:5432/finance_ai_v3"
```

### 4. Ana Servis

```python
class MyService:
    async def initialize(self):
        # Başlatma
        pass
    
    async def process(self, data):
        # İşlem
        pass
    
    async def close(self):
        # Temizlik
        pass
```

## 📝 Kod Standartları

### Python Stil Rehberi

- **PEP 8** uyumlu
- **Black** formatter kullanın
- **isort** ile import sıralaması
- **Type hints** zorunlu

### Değişken İsimlendirme

| Tür | Örnek |
|-----|-------|
| Değişken | `portfolio_id`, `ticker` |
| Fonksiyon | `get_portfolio()`, `calculate_risk()` |
| Sınıf | `PortfolioEngine`, `DecisionRecord` |
| Sabit | `MAX_POSITION_PCT`, `DEFAULT_WEIGHTS` |

### Async/Await

- Tüm veritabanı işlemleri `async/await` kullanır
- Blocking işlemler için `asyncio.to_thread()` kullanın
- Connection pool kullanımı zorunlu

## 🧪 Test Yazımı

### Test Klasör Yapısı

```
tests/
├── unit/
│   ├── test_decision_engine.py
│   └── test_portfolio_engine.py
├── integration/
│   └── test_api.py
└── fixtures/
    └── conftest.py
```

### Örnek Test

```python
import pytest
from decision_engine.service import DecisionEngineService

@pytest.fixture
def service():
    return DecisionEngineService()

@pytest.mark.asyncio
async def test_make_decision(service):
    result = await service.make_decision("portfolio_1", "THYAO")
    assert result.action in ["BUY", "SELL", "HOLD"]
```

## 📦 Bağımlılık Yönetimi

### Yeni Bağımlılık Ekleme

```bash
uv add <package>
```

### Geliştirme Bağımlılığı

```bash
uv add --dev pytest pytest-asyncio
```

## 🔒 Güvenlik

- **Hassas veriler**: Environment variable olarak saklayın
- **API anahtarları**: `.env` dosyasında tutun, asla kodlamada bırakmayın
- **Şifreler**: En az 32 karakter, karmaşık
- **JWT**: Token süresini kısa tutun (24 saat)

## 📚 Kaynaklar

- [FastAPI Dokümantasyonu](https://fastapi.tiangolo.com/)
- [asyncpg Dokümantasyonu](https://magicstack.github.io/asyncpg/)
- [Redis-py](https://redis-py.readthedocs.io/)
- [Pydantic](https://docs.pydantic.dev/)

## 🤝 Katkıda Bulunma

1. Fork edin
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add amazing feature'`)
4. Branch'i push edin (`git push origin feature/amazing-feature`)
5. Pull Request açın
