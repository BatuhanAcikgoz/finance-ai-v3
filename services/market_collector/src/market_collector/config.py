from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MarketCollectorSettings(BaseSettings):
    """Configuration for market collector service."""

    model_config = SettingsConfigDict(
        env_prefix="MARKET_COLLECTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # BIST API
    bist_api_key: str = Field(default="", description="BIST API key - must be set via environment")
    bist_api_base_url: str = "https://api.bist.com.tr/v1"
    bist_ws_url: str = "wss://ws.bist.com.tr"

    # Polling
    tick_interval_seconds: int = 10
    index_interval_seconds: int = 10

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "finance_ai_v3"
    postgres_user: str = "finance_ai_v3"
    postgres_password: str = Field(default="", description="PostgreSQL password - must be set via environment")

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = Field(default="", description="Redis password - must be set via environment")
    redis_db: int = 0

    @field_validator('bist_api_key', mode='before')
    @classmethod
    def validate_bist_api_key(cls, v: str) -> str:
        if not v:
            raise ValueError("MARKET_COLLECTOR_BIST_API_KEY must be set - BIST API key is required")
        if v == "CHANGE_ME":
            raise ValueError("MARKET_COLLECTOR_BIST_API_KEY cannot be 'CHANGE_ME' - must be set to a valid API key")
        return v

    @field_validator('postgres_password', mode='before')
    @classmethod
    def validate_postgres_password(cls, v: str) -> str:
        if v == "CHANGE_ME":
            raise ValueError("MARKET_COLLECTOR_POSTGRES_PASSWORD cannot be 'CHANGE_ME' - must be set to a valid password")
        return v

    @field_validator('redis_password', mode='before')
    @classmethod
    def validate_redis_password(cls, v: str) -> str:
        if v == "CHANGE_ME":
            raise ValueError("MARKET_COLLECTOR_REDIS_PASSWORD cannot be 'CHANGE_ME' - must be set to a valid password")
        return v

    # Timezone
    timezone: str = "Europe/Istanbul"

    # Retry
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def async_database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = MarketCollectorSettings()
