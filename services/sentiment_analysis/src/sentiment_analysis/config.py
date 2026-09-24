"""Sentiment Analysis configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class SentimentAnalysisSettings(BaseSettings):
    """Settings for Sentiment Analysis service."""

    model_config = SettingsConfigDict(
        env_prefix="SENTIMENT_ANALYSIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"
    litellm_api_base_url: str = "https://api.minimaxi.chat/v1"
    litellm_api_key: str = ""
    litellm_model: str = "MiniMax-M3"
    litellm_max_tokens: int = 300
    litellm_temperature: float = 0.1
    log_level: str = "INFO"
    idempotency_key_ttl_seconds: int = 86400


settings = SentimentAnalysisSettings()
