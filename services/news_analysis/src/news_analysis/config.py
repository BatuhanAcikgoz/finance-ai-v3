"""News Analysis configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class NewsAnalysisSettings(BaseSettings):
    """Settings for News Analysis service."""

    model_config = SettingsConfigDict(
        env_prefix="NEWS_ANALYSIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"

    # Database Configuration
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"

    # LiteLLM Configuration
    litellm_api_base_url: str = "https://api.minimaxi.chat/v1"
    litellm_api_key: str = ""
    litellm_model: str = "MiniMax-M3"
    litellm_max_tokens: int = 400
    litellm_temperature: float = 0.1

    # Logging
    log_level: str = "INFO"

    # Idempotency
    idempotency_key_ttl_seconds: int = 86400  # 24 hours

    # Processing
    max_retries: int = 1
    max_body_length: int = 6000  # Max chars from article body


settings = NewsAnalysisSettings()
