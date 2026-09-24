# Veritabanı Dokümantasyonu

Finance AI V3'ün PostgreSQL veritabanı şemaları ve tablo yapıları.

## 📋 İçindekiler

1. [Schema Organizasyonu](#schema-organizasyonu)
2. [market_data Schema](#market_data-schema)
3. [kap Schema](#kap-schema)
4. [news Schema](#news-schema)
5. [analysis Schema](#analysis-schema)
6. [portfolio Schema](#portfolio-schema)
7. [decision Schema](#decision-schema)
8. [Diğer Schemalar](#diğer-schemalar)

---

## Schema Organizasyonu

```
finance_ai_v3
├── market_data      # Piyasa verileri
├── kap              # KAP açıklamaları
├── news             # Haberler
├── tefas            # Yatırım fonları
├── macro            # Makroekonomik veriler
├── analysis         # Analiz sonuçları
├── portfolio        # Portföyler
├── decision         # Kararlar
├── risk             # Risk değerlendirmeleri
├── notification     # Bildirimler
├── audit            # Denetim
└── backtest         # Geriye dönük testler
```

---

## market_data Schema

### tickers

Hisse senedi ve endeks listesi.

```sql
CREATE TABLE market_data.tickers (
    ticker VARCHAR(5) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    sector VARCHAR(50),
    subsector VARCHAR(100),
    is_index BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| ticker | VARCHAR(5) | Hisse senedi sembolü (örn. THYAO) |
| name | VARCHAR(200) | Şirket adı |
| sector | VARCHAR(50) | Sektör |
| subsector | VARCHAR(100) | Alt sektör |
| is_index | BOOLEAN | Endeks mi? |
| is_active | BOOLEAN | Aktif mi? |

### ticks

Anlık fiyat verileri (partitioned table).

```sql
CREATE TABLE market_data.ticks (
    id BIGSERIAL,
    ticker VARCHAR(5) NOT NULL,
    price NUMERIC(18,4) NOT NULL,
    volume NUMERIC(18,4) NOT NULL,
    bid NUMERIC(18,4),
    ask NUMERIC(18,4),
    exchange_timestamp TIMESTAMPTZ NOT NULL,
    source VARCHAR(20) NOT NULL CHECK (source IN ('BIST_API', 'BIST_WS')),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, exchange_timestamp)
) PARTITION BY RANGE (exchange_timestamp);
```

### bars

OHLCV bar verileri.

```sql
CREATE TABLE market_data.bars (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(5) NOT NULL,
    timeframe VARCHAR(5) NOT NULL CHECK (timeframe IN ('1m','5m','15m','60m','1d')),
    open NUMERIC(18,4) NOT NULL,
    high NUMERIC(18,4) NOT NULL,
    low NUMERIC(18,4) NOT NULL,
    close NUMERIC(18,4) NOT NULL,
    volume NUMERIC(18,4) NOT NULL,
    bar_start TIMESTAMPTZ NOT NULL,
    bar_end TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(ticker, timeframe, bar_start)
);
```

### index_values

Endeks değerleri.

```sql
CREATE TABLE market_data.index_values (
    id BIGSERIAL PRIMARY KEY,
    index_code VARCHAR(20) NOT NULL,
    value NUMERIC(18,4) NOT NULL,
    change_pct NUMERIC(8,4),
    as_of TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(index_code, as_of)
);
```

---

## kap Schema

### disclosures

KAP açıklamaları.

```sql
CREATE TABLE kap.disclosures (
    publishing_id VARCHAR(64) PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    body TEXT NOT NULL,
    category VARCHAR(30) NOT NULL CHECK (category IN (
        'FINANCIAL_REPORT','DIVIDEND','MA','BOARD_CHANGE','CAPITAL_ACTION',
        'DISCLOSURE','MATERIAL_EVENT','GENERAL_ASSEMBLY','AUDITOR','RATING',
        'LAWSUIT','INSIDER_TRADING','OTHER'
    )),
    is_material BOOLEAN NOT NULL DEFAULT FALSE,
    material_type VARCHAR(30),
    published_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_url TEXT NOT NULL,
    classification_confidence NUMERIC(4,3),
    needs_review BOOLEAN DEFAULT FALSE,
    embedded_in_qdrant BOOLEAN DEFAULT FALSE
);
```

### disclosure_tickers

Açıklamaların ilişkili olduğu hisse senetleri.

```sql
CREATE TABLE kap.disclosure_tickers (
    publishing_id VARCHAR(64) REFERENCES kap.disclosures(publishing_id) ON DELETE CASCADE,
    ticker VARCHAR(5) NOT NULL,
    PRIMARY KEY (publishing_id, ticker)
);
```

---

## news Schema

### articles

Haber makaleleri.

```sql
CREATE TABLE news.articles (
    article_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source VARCHAR(20) NOT NULL,
    url TEXT NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    body TEXT NOT NULL,
    author VARCHAR(200),
    published_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    language VARCHAR(2) NOT NULL CHECK (language IN ('tr','en')),
    content_hash CHAR(64) NOT NULL UNIQUE
);
```

### article_tickers

Haberlerin ilişkili olduğu hisse senetleri.

```sql
CREATE TABLE news.article_tickers (
    article_id UUID REFERENCES news.articles(article_id) ON DELETE CASCADE,
    ticker VARCHAR(5) NOT NULL,
    PRIMARY KEY (article_id, ticker)
);
```

---

## analysis Schema

### technical_indicators

Hesaplanan teknik göstergeler.

```sql
CREATE TABLE analysis.technical_indicators (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(5) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    bar_start TIMESTAMPTZ NOT NULL,
    -- Trend indicators
    sma_20 NUMERIC(18,4),
    sma_50 NUMERIC(18,4),
    sma_200 NUMERIC(18,4),
    ema_12 NUMERIC(18,4),
    ema_26 NUMERIC(18,4),
    -- Momentum indicators
    rsi_14 NUMERIC(8,4),
    macd_line NUMERIC(18,4),
    macd_signal NUMERIC(18,4),
    macd_histogram NUMERIC(18,4),
    stochastic_k NUMERIC(8,4),
    stochastic_d NUMERIC(8,4),
    williams_r NUMERIC(8,4),
    cci_20 NUMERIC(8,4),
    -- Volatility indicators
    bollinger_upper NUMERIC(18,4),
    bollinger_middle NUMERIC(18,4),
    bollinger_lower NUMERIC(18,4),
    atr_14 NUMERIC(18,4),
    -- Volume indicators
    obv NUMERIC(20,4),
    vwap NUMERIC(18,4),
    adx_14 NUMERIC(8,4),
    mfi_14 NUMERIC(8,4),
    cmf_20 NUMERIC(8,4),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(ticker, timeframe, bar_start)
);
```

### technical_signals

Üretilen teknik sinyaller.

```sql
CREATE TABLE analysis.technical_signals (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(5) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    signal_type VARCHAR(50) NOT NULL,
    signal_value VARCHAR(20) NOT NULL,
    bar_start TIMESTAMPTZ NOT NULL,
    confidence NUMERIC(4,3),
    emitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(ticker, signal_type, bar_start)
);
```

### fundamental_analyses

Temel analiz sonuçları.

```sql
CREATE TABLE analysis.fundamental_analyses (
    analysis_id VARCHAR(100) PRIMARY KEY,
    ticker VARCHAR(5) NOT NULL,
    kap_publishing_id VARCHAR(64),
    direction VARCHAR(10) NOT NULL,
    strength NUMERIC(4,3),
    confidence NUMERIC(4,3),
    data_completeness VARCHAR(10),
    peer_count INTEGER,
    extracted_financials JSONB,
    ratios JSONB,
    peer_percentiles JSONB,
    reasoning TEXT,
    source_citations JSONB,
    analysis_timestamp TIMESTAMPTZ NOT NULL
);
```

---

## portfolio Schema

### portfolios

Portföyler.

```sql
CREATE TABLE portfolio.portfolios (
    portfolio_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    base_currency VARCHAR(3) DEFAULT 'TRY',
    risk_budget_pct NUMERIC(6,4) DEFAULT 0.03,
    max_position_pct NUMERIC(6,4) DEFAULT 0.25,
    max_sector_pct NUMERIC(6,4) DEFAULT 0.40,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### holdings

Portföy pozisyonları.

```sql
CREATE TABLE portfolio.holdings (
    portfolio_id UUID REFERENCES portfolio.portfolios(portfolio_id) ON DELETE CASCADE,
    ticker VARCHAR(5) NOT NULL,
    shares NUMERIC(20,4) NOT NULL,
    cost_basis_try NUMERIC(18,4),
    target_weight NUMERIC(6,4),
    current_price NUMERIC(18,4),
    current_value NUMERIC(18,4),
    unrealized_pnl NUMERIC(18,4),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (portfolio_id, ticker)
);
```

---

## decision Schema

### decisions

Trading kararları.

```sql
CREATE TABLE decision.decisions (
    decision_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL,
    ticker VARCHAR(5) NOT NULL,
    action VARCHAR(25) NOT NULL CHECK (action IN (
        'BUY','SELL','HOLD','REDUCE','INSUFFICIENT_EVIDENCE'
    )),
    confidence NUMERIC(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    position_size_pct NUMERIC(6,4) CHECK (position_size_pct BETWEEN 0 AND 0.25),
    evidence JSONB NOT NULL,
    evidence_count INTEGER NOT NULL,
    contradiction_score NUMERIC(4,3) NOT NULL,
    supervisor_reasoning TEXT,
    portfolio_context JSONB,
    compliance_status VARCHAR(10) NOT NULL CHECK (compliance_status IN (
        'PENDING','APPROVED','BLOCKED'
    )),
    compliance_reason TEXT,
    effective_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    data_completeness VARCHAR(10) NOT NULL,
    disclaimer_tr TEXT NOT NULL DEFAULT 'Bu rapor yatırım tavsiyesi değildir.',
    prompt_versions JSONB NOT NULL
);
```

**İndeksler:**

```sql
CREATE INDEX idx_decisions_portfolio_ticker ON decision.decisions(portfolio_id, ticker, effective_at DESC);
CREATE INDEX idx_decisions_compliance ON decision.decisions(compliance_status, created_at DESC);
CREATE INDEX idx_decisions_confidence ON decision.decisions(confidence DESC) WHERE compliance_status = 'APPROVED';
CREATE INDEX idx_decisions_evidence_gin ON decision.decisions USING GIN (evidence jsonb_path_ops);
```

---

## Diğer Schemalar

### tefas Schema

```sql
CREATE TABLE tefas.funds (
    fund_code VARCHAR(10) PRIMARY KEY,
    fund_name TEXT NOT NULL,
    fund_type VARCHAR(20) NOT NULL CHECK (fund_type IN (
        'MUTUAL','PARTICIPATION','GOLD','INDEX','BOND','PENSION'
    )),
    active BOOLEAN DEFAULT TRUE,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE tefas.navs (
    fund_code VARCHAR(10) REFERENCES tefas.funds(fund_code) ON DELETE CASCADE,
    nav_date DATE NOT NULL,
    nav NUMERIC(18,6) NOT NULL,
    daily_return_pct NUMERIC(8,4),
    ytd_return_pct NUMERIC(8,4),
    flow_subscription_try NUMERIC(18,2),
    flow_redemption_try NUMERIC(18,2),
    net_flow_try NUMERIC(18,2),
    total_assets_try NUMERIC(18,2),
    investor_count INTEGER,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (fund_code, nav_date)
);
```

### macro Schema

```sql
CREATE TABLE macro.indicators (
    id BIGSERIAL PRIMARY KEY,
    indicator_code VARCHAR(50) NOT NULL,
    source VARCHAR(10) NOT NULL CHECK (source IN ('TCMB','TUIKS','BDDK')),
    value NUMERIC(18,4) NOT NULL,
    unit VARCHAR(20) NOT NULL,
    release_date DATE NOT NULL,
    revised_from NUMERIC(18,4),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(indicator_code, source, release_date)
);
```

### risk Schema

```sql
CREATE TABLE risk.assessments (
    id BIGSERIAL PRIMARY KEY,
    portfolio_id UUID NOT NULL,
    var_95_1d NUMERIC(18,4),
    cvar_95_1d NUMERIC(18,4),
    portfolio_beta NUMERIC(8,4),
    portfolio_volatility NUMERIC(8,4),
    concentration_hhi NUMERIC(8,4),
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(portfolio_id, assessed_at)
);
```

### notification Schema

```sql
CREATE TABLE notification.alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker VARCHAR(5),
    portfolio_id UUID,
    grade VARCHAR(10) NOT NULL CHECK (grade IN ('INFO','WARN','CRITICAL','EMERGENCY')),
    title VARCHAR(200) NOT NULL,
    body TEXT,
    decision_id UUID REFERENCES decision.decisions(decision_id),
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### audit Schema

```sql
CREATE TABLE audit.compliance_audits (
    audit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    decision_id UUID NOT NULL REFERENCES decision.decisions(decision_id),
    compliance_status VARCHAR(10) NOT NULL,
    blocked_reason VARCHAR(50),
    violations JSONB,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    llm_check BOOLEAN DEFAULT TRUE
);
```

### backtest Schema

```sql
CREATE TABLE backtest.backtests (
    backtest_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    sample_size INTEGER NOT NULL,
    hit_rate_overall NUMERIC(4,3),
    brier_score NUMERIC(4,3),
    weight_adjustments_proposed JSONB,
    narrative_findings TEXT,
    requires_human_approval BOOLEAN DEFAULT TRUE,
    approved_by UUID,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## İndeks Stratejisi

### Önemli İndeksler

```sql
-- Piyasa verileri
CREATE INDEX idx_ticks_ticker_ts ON market_data.ticks(ticker, exchange_timestamp DESC);
CREATE INDEX idx_bars_ticker_tf_start ON market_data.bars(ticker, timeframe, bar_start DESC);
CREATE INDEX idx_index_values_code_asof ON market_data.index_values(index_code, as_of DESC);

-- KAP
CREATE INDEX idx_kap_published ON kap.disclosures(published_at DESC);
CREATE INDEX idx_kap_material ON kap.disclosures(is_material, published_at DESC) WHERE is_material;

-- Haberler
CREATE INDEX idx_news_published ON news.articles(published_at DESC);
CREATE INDEX idx_news_hash ON news.articles(content_hash);

-- Kararlar
CREATE INDEX idx_decisions_portfolio_ticker ON decision.decisions(portfolio_id, ticker, effective_at DESC);
CREATE INDEX idx_decisions_compliance ON decision.decisions(compliance_status, created_at DESC);
CREATE INDEX idx_decisions_evidence_gin ON decision.decisions USING GIN (evidence jsonb_path_ops);
```

---

## Veri Saklama Politikaları

| Tablo | Saklama Süresi |
|-------|----------------|
| ticks | 90 gün |
| bars | 2 yıl |
| index_values | 5 yıl |
| disclosures | Süresiz |
| articles | 1 yıl |
| decisions | Süresiz |
| alerts | 1 yıl |
| compliance_audits | 5 yıl |

---

## Sonraki Adımlar

- [Konfigürasyon](configuration.md) - Veritabanı konfigürasyonu
- [API Referansı](api-reference.md) - Veritabanı erişimi
