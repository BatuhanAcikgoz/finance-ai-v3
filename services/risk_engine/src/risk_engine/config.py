"""Risk Engine configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class RiskEngineSettings(BaseSettings):
    """Settings for Risk Engine service."""

    model_config = SettingsConfigDict(
        env_prefix="RISK_ENGINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"

    # Risk parameters
    var_confidence: float = 0.95
    var_period_days: int = 1
    lookback_days: int = 252  # 1 year of trading days

    # Risk budget thresholds
    max_portfolio_var_pct: float = 0.03  # 3% max daily VaR
    max_position_pct: float = 0.25  # 25% max single position
    max_sector_pct: float = 0.40  # 40% max sector exposure
    max_beta: float = 1.5

    # Alert thresholds
    var_warning_threshold: float = 0.025  # 2.5% warning
    var_critical_threshold: float = 0.04  # 4% critical
    concentration_warning_hhi: float = 0.25  # HHI > 0.25 is concentrated
    concentration_critical_hhi: float = 0.40  # HHI > 0.40 is highly concentrated

    log_level: str = "INFO"
    idempotency_key_ttl_seconds: int = 86400


settings = RiskEngineSettings()
