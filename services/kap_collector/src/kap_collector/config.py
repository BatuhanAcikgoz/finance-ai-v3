"""KAP Collector configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class KAPCollectorSettings(BaseSettings):
    """Settings for KAP Collector service."""

    model_config = SettingsConfigDict(
        env_prefix="KAP_COLLECTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # KAP API Configuration
    kap_api_base_url: str = "https://www.kap.org.tr/tr/api"
    kap_poll_interval_seconds: int = 300  # 5 minutes
    kap_max_results_per_poll: int = 100

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"

    # Database Configuration
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"

    # LiteLLM Configuration
    litellm_api_base: str = "http://localhost:4000"
    litellm_api_key: str = ""

    # Logging
    log_level: str = "INFO"

    # Idempotency
    idempotency_key_ttl_seconds: int = 86400  # 24 hours


settings = KAPCollectorSettings()
