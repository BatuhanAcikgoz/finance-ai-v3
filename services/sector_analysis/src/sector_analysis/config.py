"""Sector Analysis configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class SectorAnalysisSettings(BaseSettings):
    """Settings for Sector Analysis service."""

    model_config = SettingsConfigDict(
        env_prefix="SECTOR_ANALYSIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/finance_ai"

    # BIST sector indices
    bist_sectors: list[str] = [
        "XUMK",  # BIST Mali Endeksi (Financials)
        "XUSIN",  # BIST Sınai Endeksi (Industrial)
        "XUHIZ",  # BIST Hizmetler Endeksi (Services)
        "XUTEK",  # BIST Teknoloji Endeksi (Technology)
        "XUYLD",  # BIST Holding Endeksi (Holdings)
        "XBLSM",  # BIST Banka Endeksi (Banks)
        "XSGRT",  # BIST Sigorta Endeksi (Insurance)
        "XYAZO",  # BIST Yazılım Endeksi (Software)
        "XGIDA",  # BIST Gıda Endeksi (Food)
        "XENER",  # BIST Enerji Endeksi (Energy)
        "XMESY",  # BIST Metal Endeksi (Metal)
        "XIMKB",  # BIST İletişim Endeksi (Communication)
        "XSPOR",  # BIST Spor Endeksi (Sports)
        "XELKT",  # BIST Elektrik Endeksi (Electricity)
    ]

    # Analysis parameters
    lookback_days: int = 250
    sma_period: int = 50
    correlation_window_days: int = 90

    # Scoring thresholds
    strong_momentum_threshold: float = 0.05  # 5% monthly return
    weak_momentum_threshold: float = -0.05  # -5% monthly return
    strong_breadth_threshold: float = 0.60  # 60% above SMA
    weak_breadth_threshold: float = 0.40  # 40% above SMA

    log_level: str = "INFO"
    idempotency_key_ttl_seconds: int = 86400


settings = SectorAnalysisSettings()
