"""Backtest Agent Pydantic models."""
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class DecisionOutcome(BaseModel):
    """Decision with realized outcome."""

    decision_id: str
    ticker: str
    action: str
    confidence: float
    effective_at: str
    price_at_decision: float
    price_after_horizon: float
    actual_return: float
    predicted_direction: int  # +1 for UP, -1 for DOWN
    actual_direction: int  # +1 for UP, -1 for DOWN
    is_hit: bool


class StreamStats(BaseModel):
    """Statistics per evidence stream."""

    stream: str
    total_decisions: int
    hits: int
    misses: int
    hit_rate: float
    avg_confidence: float
    brier_score: float


class ConfidenceBucket(BaseModel):
    """Statistics per confidence bucket."""

    bucket: str  # "0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"
    total_decisions: int
    hits: int
    hit_rate: float
    avg_predicted_confidence: float
    calibration_error: float


class WeightAdjustment(BaseModel):
    """Proposed weight adjustment for an evidence stream."""

    stream: str
    current_weight: float
    proposed_weight: float
    delta: float  # Change in weight
    reason: str


class BacktestReport(BaseModel):
    """Complete backtest report."""

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    start_date: str
    end_date: str
    total_decisions: int
    overall_hit_rate: float
    overall_brier_score: float
    stream_stats: list[StreamStats]
    confidence_buckets: list[ConfidenceBucket]
    weight_adjustments: list[WeightAdjustment]
    low_sample_warning: bool = False
    critical_alert: bool = False
    calibration_issues: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    llm_narrative: str | None = None


class BacktestAudit(BaseModel):
    """Audit record for backtest runs."""

    audit_id: str = Field(default_factory=lambda: str(uuid4()))
    report_id: str
    start_date: str
    end_date: str
    total_decisions: int
    hit_rate: float
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
