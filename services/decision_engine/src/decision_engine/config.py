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

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_url: str = ""
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "finance_ai_v3"
    postgres_password: str = "dev_only_pw"
    postgres_database: str = "finance_ai_v3"
    database_url: str = ""

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

    def model_post_init(self, __context):
        """Build redis_url and database_url from component fields if not directly provided."""
        if not self.redis_url:
            auth = f":{self.redis_password}@" if self.redis_password else ""
            object.__setattr__(
                self,
                "redis_url",
                f"redis://{auth}{self.redis_host}:{self.redis_port}/0",
            )
        if not self.database_url:
            object.__setattr__(
                self,
                "database_url",
                f"postgresql://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}",
            )


settings = DecisionEngineSettings()
