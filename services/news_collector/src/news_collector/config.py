"""News Collector configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class NewsCollectorSettings(BaseSettings):
    """Settings for News Collector service."""

    model_config = SettingsConfigDict(
        env_prefix="NEWS_COLLECTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"

    # Database Configuration
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"

    # Poll Configuration
    poll_interval_seconds: int = 120  # 2 minutes
    dedup_ttl_days: int = 30

    # News Sources
    news_sources: list[str] = [
        "BLOOMBERG_HT",
        "AA",
        "FOREX",
        "REUTERS",
        "BLOOMBERG",
        "CNBC_E",
        "DUNYA",
        "CAPITAL",
        "PARA",
        "EKONOMIM",
        "PWC_TURKIYE",
        "BIGPARA",
    ]

    # Logging
    log_level: str = "INFO"

    # Idempotency
    idempotency_key_ttl_seconds: int = 86400  # 24 hours


settings = NewsCollectorSettings()
