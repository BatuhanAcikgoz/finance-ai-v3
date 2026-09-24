"""Notification Dispatch configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class NotificationDispatchSettings(BaseSettings):
    """Settings for Notification Dispatch service."""

    model_config = SettingsConfigDict(
        env_prefix="NOTIFICATION_DISPATCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"

    # Database Configuration
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"

    # SendGrid Configuration
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "noreply@financeai.example.com"
    sendgrid_from_name: str = "Finance AI V3"

    # Slack Configuration
    slack_webhook_url: str = ""

    # Rate Limiting
    max_critical_per_ticker_per_day: int = 5
    dedup_window_minutes: int = 60

    # Logging
    log_level: str = "INFO"

    # Idempotency
    idempotency_key_ttl_seconds: int = 86400  # 24 hours


settings = NotificationDispatchSettings()
