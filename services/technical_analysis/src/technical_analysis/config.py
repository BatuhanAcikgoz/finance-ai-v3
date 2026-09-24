"""Technical Analysis configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class TechnicalAnalysisSettings(BaseSettings):
    """Settings for Technical Analysis service."""

    model_config = SettingsConfigDict(
        env_prefix="TECHNICAL_ANALYSIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Redis Configuration — env-driven first, sensible dev default.
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_url: str = ""

    # Database Configuration — env-driven first, sensible dev default.
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "finance_ai_v3"
    postgres_password: str = "dev_only_pw"
    postgres_database: str = "finance_ai_v3"
    database_url: str = ""

    # Indicator Configuration
    sma_periods: list[int] = [20, 50, 200]
    ema_periods: list[int] = [12, 26]
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bollinger_period: int = 20
    bollinger_std: int = 2
    atr_period: int = 14
    stochastic_period: int = 14

    # Signal Detection
    volume_spike_threshold: float = 3.0  # Standard deviations

    # Logging
    log_level: str = "INFO"

    # Idempotency
    idempotency_key_ttl_seconds: int = 86400  # 24 hours

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


settings = TechnicalAnalysisSettings()
