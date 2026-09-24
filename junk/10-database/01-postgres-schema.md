# 10/01 — PostgreSQL Schema

> PostgreSQL 16. All schemas in database `finance_ai_v3`. Tables organized by bounded context.

## Schemas

```sql
CREATE SCHEMA IF NOT EXISTS market_data;
CREATE SCHEMA IF NOT EXISTS news;
CREATE SCHEMA IF NOT EXISTS kap;
CREATE SCHEMA IF NOT EXISTS tefas;
CREATE SCHEMA IF NOT EXISTS macro;
CREATE SCHEMA IF NOT EXISTS analysis;
CREATE SCHEMA IF NOT EXISTS portfolio;
CREATE SCHEMA IF NOT EXISTS decision;
CREATE SCHEMA IF NOT EXISTS risk;
CREATE SCHEMA IF NOT EXISTS notification;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS backtest;
```

## Core Tables

### `market_data.ticks`
```sql
CREATE TABLE market_data.ticks (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(5) NOT NULL,
    price NUMERIC(18,4) NOT NULL,
    volume NUMERIC(18,4) NOT NULL,
    bid NUMERIC(18,4),
    ask NUMERIC(18,4),
    exchange_timestamp TIMESTAMPTZ NOT NULL,
    source VARCHAR(20) NOT NULL CHECK (source IN ('BIST_API', 'BIST_WS')),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (exchange_timestamp);

CREATE INDEX idx_ticks_ticker_ts ON market_data.ticks(ticker, exchange_timestamp DESC);
```

### `market_data.bars`
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

CREATE INDEX idx_bars_ticker_tf_start ON market_data.bars(ticker, timeframe, bar_start DESC);
```

### `kap.disclosures`
```sql
CREATE TABLE kap.disclosures (
    publishing_id VARCHAR(64) PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    body TEXT NOT NULL,
    category VARCHAR(30) NOT NULL CHECK (category IN ('FINANCIAL_REPORT','DIVIDEND','MA','BOARD_CHANGE','CAPITAL_ACTION','DISCLOSURE','MATERIAL_EVENT','GENERAL_ASSEMBLY','AUDITOR','RATING','LAWSUIT','INSIDER_TRADING','OTHER')),
    is_material BOOLEAN NOT NULL DEFAULT FALSE,
    published_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_url TEXT NOT NULL,
    classification_confidence NUMERIC(4,3),
    needs_review BOOLEAN DEFAULT FALSE,
    embedded_in_qdrant BOOLEAN DEFAULT FALSE
);

CREATE TABLE kap.disclosure_tickers (
    publishing_id VARCHAR(64) REFERENCES kap.disclosures(publishing_id),
    ticker VARCHAR(5) NOT NULL,
    PRIMARY KEY (publishing_id, ticker)
);

CREATE INDEX idx_kap_published ON kap.disclosures(published_at DESC);
CREATE INDEX idx_kap_material ON kap.disclosures(is_material, published_at DESC) WHERE is_material;
```

### `news.articles`
```sql
CREATE TABLE news.articles (
    article_id UUID PRIMARY KEY,
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

CREATE TABLE news.article_tickers (
    article_id UUID REFERENCES news.articles(article_id),
    ticker VARCHAR(5) NOT NULL,
    PRIMARY KEY (article_id, ticker)
);

CREATE INDEX idx_news_published ON news.articles(published_at DESC);
CREATE INDEX idx_news_hash ON news.articles(content_hash);
```

### `tefas.funds` and `tefas.navs`
```sql
CREATE TABLE tefas.funds (
    fund_code VARCHAR(3) PRIMARY KEY,
    fund_name TEXT NOT NULL,
    fund_type VARCHAR(20) NOT NULL CHECK (fund_type IN ('MUTUAL','PARTICIPATION','GOLD','INDEX','BOND','PENSION')),
    active BOOLEAN DEFAULT TRUE,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE tefas.navs (
    fund_code VARCHAR(3) REFERENCES tefas.funds(fund_code),
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

### `analysis.technical_indicators`
```sql
CREATE TABLE analysis.technical_indicators (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(5) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    bar_start TIMESTAMPTZ NOT NULL,
    sma_20 NUMERIC(18,4),
    sma_50 NUMERIC(18,4),
    sma_200 NUMERIC(18,4),
    ema_12 NUMERIC(18,4),
    ema_26 NUMERIC(18,4),
    rsi_14 NUMERIC(8,4),
    macd_line NUMERIC(18,4),
    macd_signal NUMERIC(18,4),
    macd_histogram NUMERIC(18,4),
    bollinger_upper NUMERIC(18,4),
    bollinger_lower NUMERIC(18,4),
    atr_14 NUMERIC(18,4),
    obv NUMERIC(20,4),
    vwap NUMERIC(18,4),
    adx_14 NUMERIC(8,4),
    -- ... 20+ more
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(ticker, timeframe, bar_start)
);
```

### `decision.decisions` (the most important table)
```sql
CREATE TABLE decision.decisions (
    decision_id UUID PRIMARY KEY,
    portfolio_id UUID NOT NULL,
    ticker VARCHAR(5) NOT NULL,
    action VARCHAR(25) NOT NULL CHECK (action IN ('BUY','SELL','HOLD','REDUCE','INSUFFICIENT_EVIDENCE')),
    confidence NUMERIC(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    position_size_pct NUMERIC(6,4) NOT NULL CHECK (position_size_pct BETWEEN 0 AND 0.25),
    evidence JSONB NOT NULL,
    evidence_count INTEGER NOT NULL,
    contradiction_score NUMERIC(4,3) NOT NULL,
    supervisor_reasoning TEXT,
    portfolio_context JSONB,
    compliance_status VARCHAR(10) NOT NULL CHECK (compliance_status IN ('PENDING','APPROVED','BLOCKED')),
    compliance_reason TEXT,
    effective_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    data_completeness VARCHAR(10) NOT NULL,
    disclaimer_tr TEXT NOT NULL,
    prompt_versions JSONB NOT NULL
);

CREATE INDEX idx_decisions_portfolio_ticker ON decision.decisions(portfolio_id, ticker, effective_at DESC);
CREATE INDEX idx_decisions_compliance ON decision.decisions(compliance_status, created_at DESC);
CREATE INDEX idx_decisions_confidence ON decision.decisions(confidence DESC) WHERE compliance_status = 'APPROVED';
CREATE INDEX idx_decisions_evidence_gin ON decision.decisions USING GIN (evidence jsonb_path_ops);
```

### `portfolio.portfolios` and `portfolio.holdings`
```sql
CREATE TABLE portfolio.portfolios (
    portfolio_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    base_currency VARCHAR(3) DEFAULT 'TRY',
    risk_budget_pct NUMERIC(6,4) DEFAULT 0.03,
    max_position_pct NUMERIC(6,4) DEFAULT 0.25,
    max_sector_pct NUMERIC(6,4) DEFAULT 0.40,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE portfolio.holdings (
    portfolio_id UUID REFERENCES portfolio.portfolios(portfolio_id),
    ticker VARCHAR(5) NOT NULL,
    shares NUMERIC(20,4) NOT NULL,
    cost_basis_try NUMERIC(18,4),
    target_weight NUMERIC(6,4),
    PRIMARY KEY (portfolio_id, ticker)
);
```

### `audit.compliance_audits`
```sql
CREATE TABLE audit.compliance_audits (
    audit_id UUID PRIMARY KEY,
    decision_id UUID NOT NULL,
    compliance_status VARCHAR(10) NOT NULL,
    blocked_reason VARCHAR(50),
    violations JSONB,
    reviewed_at TIMESTAMPTZ NOT NULL,
    llm_check BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_audit_decision ON audit.compliance_audits(decision_id);
```

### `backtest.backtests`
```sql
CREATE TABLE backtest.backtests (
    backtest_id UUID PRIMARY KEY,
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
