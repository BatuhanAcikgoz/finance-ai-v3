"""Report Generator configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class ReportGeneratorSettings(BaseSettings):
    """Settings for Report Generator service."""

    model_config = SettingsConfigDict(
        env_prefix="REPORT_GENERATOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"

    # Database Configuration
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"

    # LiteLLM Configuration
    litellm_api_base: str = "http://localhost:4000"
    litellm_api_key: str = ""
    litellm_model: str = "gpt-4o-mini"

    # Report Schedules
    morning_briefing_time: str = "08:30"  # TRT
    evening_summary_time: str = "19:00"  # TRT
    weekly_summary_day: int = 5  # Friday
    weekly_summary_time: str = "19:30"  # TRT

    # Email Templates
    templates_dir: str = "services/report_generator/templates"

    # Logging
    log_level: str = "INFO"

    # Idempotency
    idempotency_key_ttl_seconds: int = 86400  # 24 hours


settings = ReportGeneratorSettings()
