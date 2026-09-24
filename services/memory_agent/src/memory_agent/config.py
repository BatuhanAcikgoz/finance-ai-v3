"""Memory Agent configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class MemoryAgentSettings(BaseSettings):
    """Settings for Memory Agent service."""

    model_config = SettingsConfigDict(
        env_prefix="MEMORY_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"
    qdrant_url: str = "http://localhost:6333"

    # Embedding settings
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072

    # Retention settings
    retention_days: int = 730  # 2 years

    # Search settings
    default_top_k: int = 10
    min_similarity_score: float = 0.7

    log_level: str = "INFO"


settings = MemoryAgentSettings()
