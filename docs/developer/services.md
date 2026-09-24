# Servisler

Finance AI V3 mikroservis mimarisindeki tüm servislerin detaylı açıklamaları.

## 📋 İçindekiler

1. [Toplama Servisleri](#toplama-servisleri)
2. [Analiz Servisleri](#analiz-servisleri)
3. [Motor Servisleri](#motor-servisleri)
4. [Destek Servisleri](#destek-servisleri)

---

## Toplama Servisleri

### Market Collector

**Lokasyon**: [`services/market_collector/`](../../services/market_collector/)

Piyasa verilerini BIST API'den toplar.

#### Özellikler

- Gerçek zamanlı fiyat verileri (tick)
- OHLCV bar verileri (1m, 5m, 15m, 60m, 1d)
- Endeks değerleri (XU100, sektör endeksleri)
- WebSocket desteği

#### Ana Metodlar

```python
class MarketCollectorService:
    async def collect_ticks(self, tickers: list[str]) -> list[dict]
    async def write_ticks(self, ticks: list[dict]) -> int
    async def collect_index_values(self) -> list[dict]
    async def run_continuous(self, tickers: list[str], interval_seconds: int = 10)
```

#### Konfigürasyon

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `BIST_API_KEY` | BIST API anahtarı | Zorunlu |
| `BIST_API_BASE_URL` | BIST API URL | https://api.bist.com.tr/v1 |

---

### KAP Collector

**Lokasyon**: [`services/kap_collector/`](../../services/kap_collector/)

KAP (Kamuyu Aydınlatma Platformu) açıklamalarını toplar.

#### Özellikler

- Mali raporlar
- Özel durum açıklamaları
- Yönetim değişiklikleri
- Temettü duyuruları

#### Desteklenen Kategoriler

```python
CATEGORIES = {
    "FINANCIAL_REPORT",
    "QUARTERLY_RESULT",
    "ANNUAL_RESULT",
    "DIVIDEND",
    "MA",
    "BOARD_CHANGE",
    "CAPITAL_ACTION",
    "DISCLOSURE",
    "MATERIAL_EVENT",
    "GENERAL_ASSEMBLY",
    "AUDITOR",
    "RATING",
}
```

---

### News Collector

**Lokasyon**: [`services/news_collector/`](../../services/news_collector/)

Finans haberlerini RSS kaynaklarından toplar.

#### Özellikler

- Çoklu RSS kaynak desteği
- Otomatik hisse senedi tanıma
- Dil tespiti (Türkçe/İngilizce)
- Content hash ile tekrar önleme

#### Varsayılan RSS Kaynakları

- Bloomberg HT
- TRT Haber
- Anadolu Ajansı
- Reuters

---

### Macro Collector

**Lokasyon**: [`services/macro_collector/`](../../services/macro_collector/)

Makroekonomik verileri TCMB, TÜİK ve BDDK'den toplar.

#### Veri Kaynakları

| Kaynak | Veri Tipi |
|--------|-----------|
| TCMB | Faiz oranları, enflasyon, DTH |
| TÜİK | GSYİH, işsizlik, sanayi üretimi |
| BDDK | Bankacılık verileri |

---

### TEFAS Collector

**Lokasyon**: [`services/tefas_collector/`](../../services/tefas_collector/)

Yatırım fonları verilerini TEFAS'tan toplar.

#### Toplanan Veriler

- FON bakiyesi (TL)
- Günlük getiri (%)
- Yıllık getiri (%)
- Dolaşımdaki pay sayısı
- Yatırımcı sayısı

---

## Analiz Servisleri

### Technical Analysis

**Lokasyon**: [`services/technical_analysis/`](../../services/technical_analysis/)

Teknik göstergeler hesaplar ve sinyaller üretir.

#### Hesaplanan Göstergeler

| Kategori | Göstergeler |
|----------|-------------|
| **Trend** | SMA 20/50/200, EMA 12/26, ADX |
| **Momentum** | RSI 14, MACD, Stochastic, Williams %R, CCI |
| **Volatilite** | Bollinger Bands, ATR |
| **Hacim** | OBV, VWAP, MFI, CMF |

#### Sinyal Türleri

```python
SIGNALS = {
    "RSI_OVERBOUGHT": "RSI > 70",
    "RSI_OVERSOLD": "RSI < 30",
    "MACD_BULLISH_CROSS": "MACD > Signal",
    "MACD_BEARISH_CROSS": "MACD < Signal",
    "BB_UPPER_BREAK": "Fiyat üst banda触碰",
    "BB_LOWER_BREAK": "Fiyat alt banda触碰",
    "SMA_BULLISH": "Fiyat SMA 20 > SMA 50",
    "SMA_BEARISH": "Fiyat SMA 20 < SMA 50",
}
```

---

### Fundamental Analysis

**Lokasyon**: [`services/fundamental_analysis/`](../../services/fundamental_analysis/)

KAP açıklamalarından mali oranlar çıkarır.

#### Çıkarılan Finansal Veriler

```python
class ExtractedFinancials:
    revenue: float       # Hasılat
    ebitda: float       # FVÖK
    net_income: float   # Net kar
    total_debt: float   # Toplam borç
    cash: float         # Nakit
    equity: float       # Öz kaynak
    eps: float          # Hisse başı kar
```

#### Hesaplanan Oranlar

| Oran | Formül |
|------|--------|
| P/E | Fiyat / Hisse Başı Kar |
| P/B | Fiyat / Defter Değeri |
| EV/EBITDA | Enterprise Value / EBITDA |
| ROE | Net Kar / Öz Kaynak |
| D/E | Toplam Borç / Öz Kaynak |

---

### Sentiment Analysis

**Lokasyon**: [`services/sentiment_analysis/`](../../services/sentiment_analysis/)

Haber ve açıklamalardan duygu analizi yapar.

#### Duygu Sınıfları

```python
class SentimentScore:
    score: float        # -1.0 (çok negatif) to +1.0 (çok pozitif)
    label: str         # "POSITIVE", "NEGATIVE", "NEUTRAL"
    conviction: float   # 0.0 to 1.0
```

---

### Sector Analysis

**Lokasyon**: [`services/sector_analysis/`](../../services/sector_analysis/)

Sektör bazlı karşılaştırmalı analiz yapar.

#### Sektör Endeksleri

- XUSIN (Sınai)
- XUMKM (Küçük ve Orta Büyüklükteki İşletmeler)
- XU030 (BIST 30)
- XUMAL (Mali)
- XUHGK (Hizmetler)
- XUIND (Tüm Endeksler)

---

## Motor Servisleri

### Decision Engine

**Lokasyon**: [`services/decision_engine/`](../../services/decision_engine/)

Kanıtları birleştirir ve trading kararları üretir.

#### Varsayılan Kanıt Ağırlıkları

```python
DEFAULT_WEIGHTS = EvidenceWeights(
    technical=0.25,
    fundamental=0.25,
    sentiment=0.15,
    sector=0.15,
    macro=0.20,
)
```

#### Karar Çıktısı

```python
class DecisionRecord:
    decision_id: UUID
    portfolio_id: UUID
    ticker: str
    action: Action  # BUY, SELL, HOLD, REDUCE
    confidence: float  # 0.0 to 1.0
    position_size_pct: float
    evidence_count: int
    contradiction_score: float
    supervisor_reasoning: str
    compliance_status: ComplianceStatus
```

---

### Portfolio Engine

**Lokasyon**: [`services/portfolio_engine/`](../../services/portfolio_engine/)

Portföy durumunu yönetir ve rebalancing önerir.

#### Metodlar

```python
class PortfolioEngineService:
    async def get_portfolio_state(self, portfolio_id: str) -> PortfolioState
    async def submit_order(self, order: Order) -> Order
    async def get_rebalance_recommendations(self, portfolio_id: str) -> list[Recommendation]
```

#### Order Durumları

```python
class OrderStatus:
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
```

---

### Risk Engine

**Lokasyon**: [`services/risk_engine/`](../../services/risk_engine/)

Risk metriklerini hesaplar.

#### Hesaplanan Metrikler

| Metrik | Açıklama |
|--------|----------|
| VaR 95% 1D | %95 güvenle 1 günde maksimum kayıp |
| CVaR 95% 1D | VaR aşıldığında ortalama kayıp |
| Portfolio Beta | Piyasa duyarlılığı |
| Volatility | Yıllıklaştırılmış standart sapma |
| Concentration HHI | Konsantrasyon endeksi |

---

### Compliance Agent

**Lokasyon**: [`services/compliance_agent/`](../../services/compliance_agent/)

Kararların yasal uyumluluğunu kontrol eder.

#### Kontrol Edilen Kurallar

1. **Yasaklı Dil**: "kesin", "garantili", "mutlak" gibi ifadeler
2. **Feragatname**: Zorunlu feragatnamenin bulunması
3. **Kanıt Atfı**: Tüm kanıtların kaynağının belirtilmesi
4. **Güven Aralığı**: 0-1 arasında olmalı
5. **Pozisyon Limiti**: Maksimum %25

---

### Backtest Agent

**Lokasyon**: [`services/backtest_agent/`](../../services/backtest_agent/)

Stratejilerin geriye dönük testini yapar.

#### Backtest Parametreleri

| Parametre | Açıklama |
|-----------|----------|
| lookback_weeks | Geriye dönük hafta sayısı |
| hit_rate_overall | Genel başarı oranı |
| brier_score | Olasılık kalibrasyonu |
| weight_adjustments | Önerilen ağırlık değişiklikleri |

---

## Destek Servisleri

### Memory Agent

**Lokasyon**: [`services/memory_agent/`](../../services/memory_agent/)

Qdrant vektör veritabanı ile benzerlik araması yapar.

#### Koleksiyonlar

```python
class CollectionType:
    NEWS = "news"
    KAP = "kap"
    DECISION = "decision"
    ANALYSIS = "analysis"
```

#### Metodlar

```python
class MemoryAgentService:
    async def embed_record(self, request: EmbedRequest) -> EmbeddingRecord
    async def search(self, request: SearchRequest) -> SimilaritySearchResponse
    async def get_similar_decisions(self, ticker: str, top_k: int = 5)
```

---

### Notification Dispatch

**Lokasyon**: [`services/notification_dispatch/`](../../services/notification_dispatch/)

E-posta ve push bildirimleri gönderir.

#### Bildirim Türleri

```python
class NotificationType:
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"  # Gelecek
```

---

### Report Generator

**Lokasyon**: [`services/report_generator/`](../../services/report_generator/)

Analiz ve karar raporları üretir.

#### Rapor Türleri

- Günlük piyasa raporu
- Portföy performans raporu
- Karar raporu
- Risk raporu
- Backtest raporu

---

## Shared Services

### Database Connection

**Lokasyon**: [`services/shared/src/shared/db/`](../../services/shared/src/shared/db/)

```python
from shared.db import get_db_pool, init_db, close_db

pool = get_db_pool()
async with pool.connection() as conn:
    result = await conn.fetch("SELECT * FROM market_data.tickers")
```

### Redis Client

**Lokasyon**: [`services/shared/src/shared/redis/`](../../services/shared/src/shared/redis/)

```python
from shared.redis import get_redis

redis = get_redis()
await redis.set_json("key", data, ttl=timedelta(seconds=30))
await redis.publish("channel", event)
```

### BIST Calendar

**Lokasyon**: [`services/shared/src/shared/calendar/`](../../services/shared/src/shared/calendar/)

```python
from shared.calendar import is_market_open, is_trading_day

if is_market_open():
    # Piyasa açık
```

---

## Sonraki Adımlar

- [Veritabanı Şemaları](database.md) - Detaylı tablo yapıları
- [Konfigürasyon](configuration.md) - Environment değişkenleri
- [API Referansı](api-reference.md) - Tüm endpointler
