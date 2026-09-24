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

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"

    # Database Configuration
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"

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


settings = TechnicalAnalysisSettings()
