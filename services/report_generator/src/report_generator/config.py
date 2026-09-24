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

    # Redis Configuration — env-driven first, sensible dev default.
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_url: str = ""

    # Database Configuration — env-driven first, sensible dev default.
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "finance_ai_v3"
    postgres_password: str = "dev_only_pw"
    postgres_database: str = "finance_ai_v3"
    database_url: str = ""

    # LiteLLM Configuration
    litellm_api_base: str = "http://litellm:4000"
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

    def model_post_init(self, __context):
        """Build redis_url and database_url from component fields if not directly provided."""
        if not self.redis_url:
            auth = f":{self.redis_password}@" if self.redis_password else ""
            object.__setattr__(
                self,
                "redis_url",
                f"redis://{auth}{self.redis_host}:{self.redis_port}/0",
            )
        if not self.database_url:
            object.__setattr__(
                self,
                "database_url",
                f"postgresql://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}",
            )


settings = ReportGeneratorSettings()
