"""Pydantic models for Macro Analysis."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Regime(str, Enum):
    """Market regime."""

    BULL = "BULL"
    BEAR = "BEAR"
    RANGE = "RANGE"
    CRISIS = "CRISIS"


class Source(str, Enum):
    """Macro data source."""

    TCMB = "TCMB"
    TUIKS = "TUIKS"
    BDDK = "BDDK"


class DataCompleteness(str, Enum):
    """Data completeness status."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class ImpactEstimates(BaseModel):
    """Impact estimates on market indicators."""

    bist100_1d_pct: float = Field(ge=-0.05, le=0.05)
    usdtry_1d_pct: float = Field(ge=-0.05, le=0.05)
    banking_sector_1d_pct: float = Field(ge=-0.05, le=0.05)


class MacroAnalysisResult(BaseModel):
    """Output of macro analysis agent."""

    indicator_code: str
    source: Source
    release_date: datetime
    actual_value: float | None = None
    consensus_value: float | None = None
    surprise: float | None = None
    regime: Regime
    regime_changed: bool = False
    impact_estimates: ImpactEstimates
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    data_completeness: DataCompleteness
    analysis_timestamp: datetime = Field(default_factory=lambda: datetime.now())
    llm_tokens_in: int | None = None
    llm_tokens_out: int | None = None
    cost_usd: float | None = None


class MacroUpdateEvent(BaseModel):
    """Input event from macro collector."""

    event_type: str = "raw.macro.update"
    indicator_code: str
    source: str
    value: float
    unit: str
    release_date: str
    timestamp: str


class MacroAnalysisDBRecord(BaseModel):
    """Record to be stored in PostgreSQL."""

    analysis_id: str
    indicator_code: str
    source: Source
    release_date: datetime
    actual_value: float | None
    consensus_value: float | None
    surprise: float | None
    regime: Regime
    regime_changed: bool
    impact_estimates_json: str
    confidence: float
    reasoning: str
    data_completeness: DataCompleteness
    analysis_timestamp: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now())
