"""Portfolio Engine configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class PortfolioEngineSettings(BaseSettings):
    """Settings for Portfolio Engine service."""

    model_config = SettingsConfigDict(
        env_prefix="PORTFOLIO_ENGINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"

    # Trading hours (TRT)
    trading_start_hour: int = 10
    trading_end_hour: int = 18

    # Position constraints
    max_position_pct: float = 0.25  # 25% max single position
    max_sector_pct: float = 0.40  # 40% max sector exposure
    min_trade_value_try: float = 100.0  # Min trade size
    max_trade_value_try: float = 1_000_000.0  # Max trade size

    # Rebalancing
    rebalance_threshold_pct: float = 0.05  # 5% drift triggers rebalance
    kelly_fraction: float = 0.25  # Kelly criterion fraction to use

    # Order execution
    order_timeout_seconds: int = 30
    max_slippage_bps: int = 50  # 50 basis points max slippage

    log_level: str = "INFO"
    idempotency_key_ttl_seconds: int = 3600


settings = PortfolioEngineSettings()
