"""Decision Engine Pydantic models."""
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Action(str, Enum):
    """Trading action."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class MarketRegime(str, Enum):
    """Market regime classification."""

    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    SIDEWAYS = "SIDEWAYS"
    VOLATILE = "VOLATILE"
    UNKNOWN = "UNKNOWN"


class Urgency(str, Enum):
    """Decision urgency level."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ComplianceStatus(str, Enum):
    """Compliance status."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"


class DataCompleteness(str, Enum):
    """Data completeness status."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class EvidenceStream(str, Enum):
    """Evidence stream types."""

    TECHNICAL = "TECHNICAL"
    FUNDAMENTAL = "FUNDAMENTAL"
    MACRO = "MACRO"
    NEWS = "NEWS"
    SENTIMENT = "SENTIMENT"
    SECTOR = "SECTOR"
    PORTFOLIO = "PORTFOLIO"
    SIMILARITY = "SIMILARITY"


class Signal(str, Enum):
    """Trading signal."""

    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"


class Evidence(BaseModel):
    """Single piece of evidence for a decision."""

    stream: EvidenceStream
    signal: Signal
    strength: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PortfolioContext(BaseModel):
    """Portfolio context for position sizing and risk management."""

    current_weight: float = Field(..., ge=0.0, le=1.0)
    post_trade_weight: float = Field(..., ge=0.0, le=1.0)
    kelly_fraction: float = Field(..., ge=0.0, le=1.0)
    drift_pct: float = Field(..., ge=-1.0, le=1.0)

    # Cost basis tracking - CRITICAL for decision making
    avg_cost: float = Field(default=0.0, ge=0.0, description="Average cost basis per share in TRY")
    current_price: float = Field(default=0.0, ge=0.0, description="Current market price")
    unrealized_pnl_try: float = Field(default=0.0, description="Unrealized P&L in TRY")
    unrealized_pnl_pct: float = Field(default=0.0, ge=-1.0, le=10.0, description="Unrealized P&L percentage")
    quantity: int = Field(default=0, ge=0, description="Number of shares/lots")

    # Risk indicators
    consecutive_red_days: int = Field(default=0, ge=0, description="Consecutive losing days")
    market_crash: bool = Field(default=False, description="Market crash detected flag")
    sector_exposure: float = Field(default=0.0, ge=0.0, le=1.0, description="Total exposure in same sector")

    # Position metadata
    position_open_date: str | None = Field(default=None, description="Date position was opened")
    last_price_update: str | None = Field(default=None, description="Last price update timestamp")


class TechnicalIndicators(BaseModel):
    """Raw technical indicators for decision making."""

    rsi: float = Field(default=50.0, ge=0.0, le=100.0, description="RSI 14 period")
    macd: float = Field(default=0.0, description="MACD line value")
    macd_signal: float = Field(default=0.0, description="MACD signal line")
    macd_histogram: float = Field(default=0.0, description="MACD histogram")
    sma_20: float = Field(default=0.0, description="20-period SMA")
    sma_50: float = Field(default=0.0, description="50-period SMA")
    sma_200: float = Field(default=0.0, description="200-period SMA")
    price_vs_sma_pct: float = Field(default=0.0, description="Current price vs SMA percentage")
    bollinger_upper: float = Field(default=0.0, description="Bollinger upper band")
    bollinger_lower: float = Field(default=0.0, description="Bollinger lower band")
    volume_ratio: float = Field(default=1.0, description="Volume vs average ratio")
    atr: float = Field(default=0.0, description="Average True Range")
    adx: float = Field(default=0.0, ge=0.0, le=100.0, description="Average Directional Index")


class MarketContext(BaseModel):
    """Market-wide context for regime detection."""

    index_value: float = Field(default=0.0, description="BIST-100 index value")
    index_change_pct: float = Field(default=0.0, description="Daily index change percentage")
    sector_index: float = Field(default=0.0, description="Relevant sector index value")
    sector_change_pct: float = Field(default=0.0, description="Sector daily change")
    regime: MarketRegime = Field(default=MarketRegime.UNKNOWN, description="Detected market regime")
    volatility: float = Field(default=0.0, description="Market volatility measure")
    usd_try: float = Field(default=0.0, description="USD/TRY exchange rate")
    usd_try_change: float = Field(default=0.0, description="USD/TRY daily change")


class DecisionFactors(BaseModel):
    """Multi-variable decision factors for comprehensive analysis."""

    signal_score: float = Field(default=0.0, ge=-1.0, le=1.0, description="Aggregated signal score")
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Risk assessment score")
    momentum_score: float = Field(default=0.0, ge=-1.0, le=1.0, description="Price momentum score")
    value_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Value assessment score")
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0, description="Sentiment score")
    regime_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Market regime alignment score")


class AggregatedEvidence(BaseModel):
    """Result of evidence aggregation."""

    weighted_signal: float = Field(..., ge=-1.0, le=1.0)
    evidence_count: int = Field(..., ge=0)
    contradiction_score: float = Field(..., ge=0.0, le=1.0)
    insufficient: bool = False


class DecisionRecord(BaseModel):
    """Complete decision record with multi-variable analysis."""

    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    portfolio_id: str
    ticker: str
    action: Action
    urgency: Urgency = Urgency.MEDIUM
    confidence: float = Field(..., ge=0.0, le=1.0)
    position_size_pct: float = Field(..., ge=0.0, le=0.25)
    evidence: list[Evidence] = Field(default_factory=list)
    evidence_count: int = 0
    contradiction_score: float = 0.0
    supervisor_reasoning: str = ""
    
    # Enhanced context
    portfolio_context: PortfolioContext | None = None
    technical_indicators: TechnicalIndicators | None = None
    market_context: MarketContext | None = None
    decision_factors: DecisionFactors | None = None
    
    # Risk management
    stop_loss_price: float | None = Field(default=None, description="Stop-loss price level")
    take_profit_price: float | None = Field(default=None, description="Take-profit price level")
    risk_reward_ratio: float | None = Field(default=None, description="Risk/reward ratio")
    
    # Execution
    compliance_status: ComplianceStatus = ComplianceStatus.PENDING
    compliance_reason: str | None = None
    effective_at: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    data_completeness: DataCompleteness = DataCompleteness.PARTIAL
    disclaimer_tr: str = "Bu yatırım kararı bilgilendirme amaçlıdır. Yatırım danışmanlığı değildir."
    prompt_versions: dict[str, str] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization processing."""
        self.evidence_count = len(self.evidence)


class DecisionRequest(BaseModel):
    """Request to make a decision."""

    portfolio_id: str
    ticker: str
    evidence: list[Evidence]


class DecisionResponse(BaseModel):
    """Response containing decision record."""

    decision: DecisionRecord
    aggregated_evidence: AggregatedEvidence


class EvidenceWeights(BaseModel):
    """Evidence weights for aggregation."""

    technical: float = 0.20
    fundamental: float = 0.25
    macro: float = 0.20
    sentiment: float = 0.15
    sector: float = 0.10
    news: float = 0.10

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary with stream keys."""
        return {
            "TECHNICAL": self.technical,
            "FUNDAMENTAL": self.fundamental,
            "MACRO": self.macro,
            "SENTIMENT": self.sentiment,
            "SECTOR": self.sector,
            "NEWS": self.news,
        }
