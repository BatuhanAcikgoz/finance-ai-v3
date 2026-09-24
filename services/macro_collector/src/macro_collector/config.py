"""Macro Collector configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class MacroCollectorSettings(BaseSettings):
    """Settings for Macro Collector service."""

    model_config = SettingsConfigDict(
        env_prefix="MACRO_COLLECTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # TCMB EVDS API Configuration
    tcmb_evds_base_url: str = "https://evds2.tcmb.gov.tr"
    tcmb_api_key: str = ""

    # TÜİK Configuration
    tuik_base_url: str = "https://www.tuik.gov.tr"
    
    # BDDK Configuration
    bddk_base_url: str = "https://www.bddk.org.tr"

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"

    # Database Configuration
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"

    # Polling schedules
    tcmb_poll_hour: int = 11  # 11:00 TRT
    tuik_poll_after_release_hour: int = 14  # 14:00 TRT
    bddk_poll_day_of_week: int = 1  # Monday

    # Logging
    log_level: str = "INFO"

    # Idempotency
    idempotency_key_ttl_seconds: int = 86400  # 24 hours


settings = MacroCollectorSettings()
