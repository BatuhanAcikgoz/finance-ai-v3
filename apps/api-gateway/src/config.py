"""Application configuration.

Reads POSTGRES_*, REDIS_*, QDRANT_* env vars (matching ``infra/docker/.env.docker``
and ``.env.example``). Designed to be import-safe: a missing optional secret
does NOT crash the process. Health endpoint reports degraded mode instead.
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """API Gateway settings — bare env vars (POSTGRES_HOST, REDIS_HOST, ...)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application ----
    app_name: str = "Finance AI V3 API"
    app_version: str = "0.1.0"
    debug: bool = False
    api_env: str = "development"

    # ---- Postgres ----
    # Hostname defaults to "localhost" so non-docker `uv run` works out of the box.
    # Inside docker-compose the service name is "postgres" — set POSTGRES_HOST=postgres.
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "finance_ai_v3"
    postgres_user: str = "finance_ai_v3"
    postgres_password: str = ""
    postgres_max_connections: int = 20

    # ---- Redis ----
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # ---- Qdrant ----
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_grpc_port: int = 6334
    qdrant_api_key: str = ""
    qdrant_collection_prefix: str = "finance_ai_v3"

    # ---- Security / Auth (optional in dev) ----
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440
    rate_limit_per_minute: int = 100

    # ---- Optional: full DSN overrides ----
    # If set, overrides individual components above. Useful for prod where a
    # single connection string is injected.
    postgres_dsn: Optional[str] = None
    redis_url_override: Optional[str] = None

    # -- derived URLs -------------------------------------------------------

    @property
    def async_database_url(self) -> str:
        """DSN accepted by ``asyncpg.create_pool`` (no SQLAlchemy prefix)."""
        if self.postgres_dsn:
            # Strip optional +asyncpg / +psycopg prefix if present.
            dsn = self.postgres_dsn
            for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://"):
                if dsn.startswith(prefix):
                    dsn = "postgresql://" + dsn[len(prefix):]
                    break
            return dsn
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_url_override:
            return self.redis_url_override
        if self.redis_password:
            return (
                f"redis://:{self.redis_password}@{self.redis_host}:"
                f"{self.redis_port}/{self.redis_db}"
            )
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def qdrant_evidence_collection(self) -> str:
        return f"{self.qdrant_collection_prefix}_evidence"

    @property
    def qdrant_headers(self) -> dict[str, str]:
        if not self.qdrant_api_key:
            return {}
        return {"api-key": self.qdrant_api_key}


# Module-level singleton — import-safe (no validators that can raise).
settings = Settings()