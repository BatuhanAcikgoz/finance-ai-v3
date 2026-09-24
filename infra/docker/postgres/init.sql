-- =============================================================================
-- Finance AI V3 - PostgreSQL Initialization
-- =============================================================================
-- This script runs on first start to create schemas and extensions

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================================================
-- Schemas
-- =============================================================================
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

-- =============================================================================
-- market_data schema
-- =============================================================================

-- Tickers table
CREATE TABLE IF NOT EXISTS market_data.tickers (
    ticker VARCHAR(5) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    sector VARCHAR(50),
    subsector VARCHAR(100),
    is_index BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ticks table (partitioned by time)
CREATE TABLE IF NOT EXISTS market_data.ticks (
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

-- Create initial partition for current month
CREATE TABLE IF NOT EXISTS market_data.ticks_current PARTITION OF market_data.ticks
    FOR VALUES FROM (CURRENT_DATE - INTERVAL '1 month') TO (CURRENT_DATE + INTERVAL '2 months');

-- Index on ticks
CREATE INDEX IF NOT EXISTS idx_ticks_ticker_ts ON market_data.ticks(ticker, exchange_timestamp DESC);

-- Bars table
CREATE TABLE IF NOT EXISTS market_data.bars (
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

CREATE INDEX IF NOT EXISTS idx_bars_ticker_tf_start ON market_data.bars(ticker, timeframe, bar_start DESC);

-- Index values table
CREATE TABLE IF NOT EXISTS market_data.index_values (
    id BIGSERIAL PRIMARY KEY,
    index_code VARCHAR(20) NOT NULL,
    value NUMERIC(18,4) NOT NULL,
    change_pct NUMERIC(8,4),
    as_of TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(index_code, as_of)
);

CREATE INDEX IF NOT EXISTS idx_index_values_code_asof ON market_data.index_values(index_code, as_of DESC);

-- =============================================================================
-- kap schema (KAP Disclosures)
-- =============================================================================

CREATE TABLE IF NOT EXISTS kap.disclosures (
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

CREATE TABLE IF NOT EXISTS kap.disclosure_tickers (
    publishing_id VARCHAR(64) REFERENCES kap.disclosures(publishing_id) ON DELETE CASCADE,
    ticker VARCHAR(5) NOT NULL,
    PRIMARY KEY (publishing_id, ticker)
);

CREATE INDEX IF NOT EXISTS idx_kap_published ON kap.disclosures(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_kap_material ON kap.disclosures(is_material, published_at DESC) WHERE is_material;

-- =============================================================================
-- news schema
-- =============================================================================

CREATE TABLE IF NOT EXISTS news.articles (
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

CREATE TABLE IF NOT EXISTS news.article_tickers (
    article_id UUID REFERENCES news.articles(article_id) ON DELETE CASCADE,
    ticker VARCHAR(5) NOT NULL,
    PRIMARY KEY (article_id, ticker)
);

CREATE TABLE IF NOT EXISTS news.article_sectors (
    article_id UUID REFERENCES news.articles(article_id) ON DELETE CASCADE,
    sector VARCHAR(50) NOT NULL,
    PRIMARY KEY (article_id, sector)
);

CREATE INDEX IF NOT EXISTS idx_news_published ON news.articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_hash ON news.articles(content_hash);

-- =============================================================================
-- tefas schema (TEFAS Funds)
-- =============================================================================

CREATE TABLE IF NOT EXISTS tefas.funds (
    fund_code VARCHAR(10) PRIMARY KEY,
    fund_name TEXT NOT NULL,
    fund_type VARCHAR(20) NOT NULL CHECK (fund_type IN ('MUTUAL','PARTICIPATION','GOLD','INDEX','BOND','PENSION')),
    active BOOLEAN DEFAULT TRUE,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tefas.navs (
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

CREATE INDEX IF NOT EXISTS idx_tefas_navs_date ON tefas.navs(nav_date DESC);

-- =============================================================================
-- macro schema (Macroeconomic indicators)
-- =============================================================================

CREATE TABLE IF NOT EXISTS macro.indicators (
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

CREATE INDEX IF NOT EXISTS idx_macro_indicators_code_date ON macro.indicators(indicator_code, release_date DESC);

-- =============================================================================
-- analysis schema (Technical & Fundamental Analysis)
-- =============================================================================

CREATE TABLE IF NOT EXISTS analysis.technical_indicators (
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

CREATE INDEX IF NOT EXISTS idx_tech_indicators_ticker_tf_start ON analysis.technical_indicators(ticker, timeframe, bar_start DESC);

CREATE TABLE IF NOT EXISTS analysis.technical_signals (
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

CREATE INDEX IF NOT EXISTS idx_tech_signals_ticker ON analysis.technical_signals(ticker, emitted_at DESC);

-- =============================================================================
-- portfolio schema
-- =============================================================================

CREATE TABLE IF NOT EXISTS portfolio.portfolios (
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

CREATE TABLE IF NOT EXISTS portfolio.holdings (
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

CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolio.portfolios(user_id);

-- =============================================================================
-- decision schema (Decision Records)
-- =============================================================================

CREATE TABLE IF NOT EXISTS decision.decisions (
    decision_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL,
    ticker VARCHAR(5) NOT NULL,
    action VARCHAR(25) NOT NULL CHECK (action IN ('BUY','SELL','HOLD','REDUCE','INSUFFICIENT_EVIDENCE')),
    confidence NUMERIC(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    position_size_pct NUMERIC(6,4) CHECK (position_size_pct BETWEEN 0 AND 0.25),
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
    disclaimer_tr TEXT NOT NULL DEFAULT 'Bu rapor yatırım tavsiyesi değildir. Yatırım kararlarınızı kendi araştırmanızla destekleyiniz.',
    prompt_versions JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decisions_portfolio_ticker ON decision.decisions(portfolio_id, ticker, effective_at DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_compliance ON decision.decisions(compliance_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_confidence ON decision.decisions(confidence DESC) WHERE compliance_status = 'APPROVED';
CREATE INDEX IF NOT EXISTS idx_decisions_evidence_gin ON decision.decisions USING GIN (evidence jsonb_path_ops);

-- =============================================================================
-- risk schema (Risk Assessments)
-- =============================================================================

CREATE TABLE IF NOT EXISTS risk.assessments (
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

CREATE INDEX IF NOT EXISTS idx_risk_assessments_portfolio ON risk.assessments(portfolio_id, assessed_at DESC);

-- =============================================================================
-- notification schema (Alerts & Notifications)
-- =============================================================================

CREATE TABLE IF NOT EXISTS notification.alerts (
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

CREATE INDEX IF NOT EXISTS idx_alerts_portfolio ON notification.alerts(portfolio_id, created_at DESC) WHERE portfolio_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_alerts_ticker ON notification.alerts(ticker, created_at DESC) WHERE ticker IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_alerts_unread ON notification.alerts(is_read, created_at DESC) WHERE NOT is_read;

-- =============================================================================
-- audit schema (Compliance Audits)
-- =============================================================================

CREATE TABLE IF NOT EXISTS audit.compliance_audits (
    audit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    decision_id UUID NOT NULL REFERENCES decision.decisions(decision_id),
    compliance_status VARCHAR(10) NOT NULL,
    blocked_reason VARCHAR(50),
    violations JSONB,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    llm_check BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_audit_decision ON audit.compliance_audits(decision_id);

-- =============================================================================
-- backtest schema (Backtest Results)
-- =============================================================================

CREATE TABLE IF NOT EXISTS backtest.backtests (
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

-- =============================================================================
-- workflow_audit schema (Workflow Execution Tracking)
-- =============================================================================

CREATE TABLE IF NOT EXISTS audit.workflow_executions (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_name VARCHAR(100) NOT NULL,
    idempotency_key VARCHAR(200),
    status VARCHAR(20) NOT NULL CHECK (status IN ('STARTED','COMPLETED','FAILED','RETRYING')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    input_payload JSONB,
    output_payload JSONB
);

CREATE INDEX IF NOT EXISTS idx_workflow_executions_name ON audit.workflow_executions(workflow_name, started_at DESC);

-- =============================================================================
-- Grant permissions (assuming same user)
-- =============================================================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA market_data TO finance_ai_v3;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA news TO finance_ai_v3;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA kap TO finance_ai_v3;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA tefas TO finance_ai_v3;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA macro TO finance_ai_v3;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA analysis TO finance_ai_v3;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA portfolio TO finance_ai_v3;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA decision TO finance_ai_v3;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA risk TO finance_ai_v3;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA notification TO finance_ai_v3;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA audit TO finance_ai_v3;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA backtest TO finance_ai_v3;
