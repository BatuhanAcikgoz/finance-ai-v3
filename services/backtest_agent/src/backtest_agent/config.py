"""Backtest Agent configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class BacktestAgentSettings(BaseSettings):
    """Settings for Backtest Agent service."""

    model_config = SettingsConfigDict(
        env_prefix="BACKTEST_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"

    # Backtest parameters
    lookback_weeks: int = 4
    min_sample_size: int = 30
    horizon_days: int = 5  # Days to hold before measuring outcome
    max_weight_adjustment: float = 0.20  # Max ±20% weight change per stream

    # Hit-rate thresholds
    hit_rate_critical_threshold: float = 0.50  # Below 50% is critical
    calibration_error_threshold: float = 0.15  # Above 15% calibration error

    log_level: str = "INFO"


settings = BacktestAgentSettings()
