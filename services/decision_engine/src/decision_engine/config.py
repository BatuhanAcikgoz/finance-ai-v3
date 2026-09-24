"""Decision Engine configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class DecisionEngineSettings(BaseSettings):
    """Settings for Decision Engine service."""

    model_config = SettingsConfigDict(
        env_prefix="DECISION_ENGINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"
    
    # Evidence weights per stream
    technical_weight: float = 0.20
    fundamental_weight: float = 0.25
    macro_weight: float = 0.20
    sentiment_weight: float = 0.15
    sector_weight: float = 0.10
    news_weight: float = 0.10
    
    # Decision thresholds
    confidence_threshold: float = 0.60
    min_evidence_count: int = 2
    
    # Grades
    info_threshold: float = 0.50
    warn_threshold: float = 0.70
    critical_threshold: float = 0.85
    emergency_threshold: float = 0.95
    
    # Report schedule (TRT = UTC+3)
    morning_report_hour: int = 10   # 10:00 TRT - market open analysis
    evening_report_hour: int = 17   # 17:00 TRT - pre-close analysis
    bist_open_hour: int = 10        # BIST market open
    bist_close_hour: int = 18       # BIST market close
    
    # Risk management thresholds
    stop_loss_pct: float = 0.10     # 10% stop-loss
    take_profit_pct: float = 0.20   # 20% take-profit
    max_sector_exposure: float = 0.30  # Max 30% in one sector
    max_position_weight: float = 0.25   # Max 25% single position
    max_daily_trades: int = 5        # Max 5 trades per day
    max_daily_loss_pct: float = 0.03  # Max 3% daily loss
    
    # Market regime detection
    adx_strong_trend: float = 25.0  # ADX > 25 = trending
    volatility_threshold: float = 2.0  # ATR percentage threshold
    
    log_level: str = "INFO"
    idempotency_key_ttl_seconds: int = 86400


settings = DecisionEngineSettings()
