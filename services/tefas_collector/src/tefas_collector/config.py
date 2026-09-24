"""TEFAS Collector configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class TEFASCollectorSettings(BaseSettings):
    """Settings for TEFAS Collector service."""

    model_config = SettingsConfigDict(
        env_prefix="TEFAS_COLLECTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # TEFAS API Configuration
    tefas_api_base_url: str = "https://www.tefas.gov.tr/api"
    poll_interval_hours: int = 24  # Daily

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"

    # Database Configuration
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"

    # Logging
    log_level: str = "INFO"

    # Idempotency
    idempotency_key_ttl_seconds: int = 86400  # 24 hours


settings = TEFASCollectorSettings()
