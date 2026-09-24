"""Compliance Agent configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class ComplianceAgentSettings(BaseSettings):
    """Settings for Compliance Agent service."""

    model_config = SettingsConfigDict(
        env_prefix="COMPLIANCE_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"

    # Forbidden language patterns (Turkish + English)
    forbidden_patterns: list[str] = [
        r"garante\w*\s*(getiri|return|kazanç)",
        r"%100\s*(kesin|kesinlikle|certain)",
        r"risksiz\s*(yatırım|investment)",
        r"kesin\s*(kazanç|getiri|win)",
        r"mutlak\s*(kazanç|getiri)",
        r"sure\s*thing",
        r"100%\s*certain",
        r"risk[- ]free",
        r"guaranteed\s*(return|profit)",
    ]

    # Disclaimer text
    disclaimer_tr: str = "Bu yatırım kararı bilgilendirme amaçlıdır. Yatırım danışmanlığı değildir. Geçmiş performans gelecekteki sonuçların garantisi değildir."

    # Block reasons
    block_reasons: list[str] = [
        "FORBIDDEN_LANGUAGE",
        "MISSING_DISCLAIMER",
        "MISSING_EVIDENCE_CITATION",
        "INVALID_CONFIDENCE",
        "POSITION_CONSTRAINT_VIOLATION",
        "UNCLEAR_PAYLOAD",
    ]

    log_level: str = "INFO"


settings = ComplianceAgentSettings()
