"""Sector Analysis Pydantic models."""
from enum import Enum

from pydantic import BaseModel, Field


class Signal(str, Enum):
    """Trading signal."""

    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"


class SectorReturn(BaseModel):
    """Sector return metrics."""

    ticker: str
    period_1d: float = Field(..., description="1-day return as decimal")
    period_1w: float = Field(..., description="1-week return as decimal")
    period_1m: float = Field(..., description="1-month return as decimal")
    period_3m: float = Field(..., description="3-month return as decimal")
    period_ytd: float = Field(..., description="Year-to-date return as decimal")


class SectorBreadth(BaseModel):
    """Sector breadth metrics (% of constituents above indicators)."""

    ticker: str
    above_sma50_pct: float = Field(..., ge=0.0, le=1.0)
    above_sma200_pct: float = Field(..., ge=0.0, le=1.0)


class SectorRelativeStrength(BaseModel):
    """Relative strength vs BIST-100."""

    ticker: str
    rs_1m: float = Field(..., description="1-month relative strength")
    rs_3m: float = Field(..., description="3-month relative strength")
    rs_ytd: float = Field(..., description="YTD relative strength")


class SectorScore(BaseModel):
    """Final sector score and ranking."""

    ticker: str
    total_score: float = Field(..., ge=-1.0, le=1.0, description="Composite score")
    momentum_score: float = Field(..., ge=0.0, le=1.0)
    breadth_score: float = Field(..., ge=0.0, le=1.0)
    relative_strength_score: float = Field(..., ge=0.0, le=1.0)
    rank: int = Field(..., ge=1, le=14, description="Rank among 14 sectors")
    signal: Signal


class SectorAnalysisResult(BaseModel):
    """Complete sector analysis result."""

    analysis_id: str
    analyzed_at: str
    sector_scores: list[SectorScore]
    correlation_matrix: list[list[float]] | None = None
    is_weekly_correlation_update: bool = False
    data_completeness: str = Field(..., pattern="^(complete|partial|missing)$")


class SectorAnalysisEvent(BaseModel):
    """Redis event emitted after sector analysis."""

    event_type: str = "analysis.sector.complete"
    analysis_id: str
    analyzed_at: str
    top_sectors: list[str] = Field(..., max_length=3)
    bottom_sectors: list[str] = Field(..., max_length=3)
    is_weekly_update: bool = False


class SectorDataPoint(BaseModel):
    """Single sector data point for analysis."""

    ticker: str
    date: str
    close: float
    volume: float | None = None
