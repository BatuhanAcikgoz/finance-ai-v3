"""Pydantic models for Fundamental Analysis."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Direction(str, Enum):
    """Signal direction."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class DataCompleteness(str, Enum):
    """Data completeness status."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class SourceCitation(BaseModel):
    """Citation for an extracted financial value."""

    field: str
    kap_id: str
    line_no: int


class ExtractedFinancials(BaseModel):
    """Financial metrics extracted from KAP disclosure."""

    revenue: float | None = None
    ebitda: float | None = None
    net_income: float | None = None
    total_debt: float | None = None
    cash: float | None = None
    equity: float | None = None
    eps: float | None = None
    source_citations: list[SourceCitation] = Field(default_factory=list)


class PeerPercentiles(BaseModel):
    """Peer comparison percentiles."""

    pe_percentile: float | None = None
    pb_percentile: float | None = None
    roe_percentile: float | None = None


class FundamentalRatios(BaseModel):
    """Computed fundamental ratios."""

    # Market ratios
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
    ev_ebitda: float | None = None
    ev_sales: float | None = None

    # Profitability ratios
    roe: float | None = None
    roa: float | None = None
    roic: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None

    # Leverage ratios
    debt_equity: float | None = None
    debt_assets: float | None = None
    current_ratio: float | None = None
    quick_ratio: float | None = None

    # Growth ratios (YoY)
    revenue_growth: float | None = None
    earnings_growth: float | None = None

    # Valuation flags
    pe_flagged: bool = False  # True if P/E > 100 or < 0


class FundamentalAnalysisResult(BaseModel):
    """Output of fundamental analysis agent."""

    ticker: str
    kap_publishing_id: str
    direction: Direction
    strength: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    extracted_financials: ExtractedFinancials
    ratios: FundamentalRatios = Field(default_factory=FundamentalRatios)
    peer_percentiles: PeerPercentiles | None = None
    peer_count: int = 0
    reasoning: str
    data_completeness: DataCompleteness
    source_citations: list[SourceCitation] = Field(default_factory=list)
    analysis_timestamp: datetime = Field(default_factory=lambda: datetime.now())
    llm_tokens_in: int | None = None
    llm_tokens_out: int | None = None
    cost_usd: float | None = None


class KAPMaterialEvent(BaseModel):
    """Input event from KAP collector for material disclosures."""

    event_type: str = "raw.kap.material"
    publishing_id: str
    title: str
    category: str
    tickers: list[str]
    timestamp: str


class FundamentalAnalysisDBRecord(BaseModel):
    """Record to be stored in PostgreSQL."""

    analysis_id: str
    ticker: str
    kap_publishing_id: str
    direction: Direction
    strength: float
    confidence: float
    data_completeness: DataCompleteness
    peer_count: int
    extracted_financials_json: str  # JSON serialized
    ratios_json: str  # JSON serialized
    peer_percentiles_json: str | None  # JSON serialized
    reasoning: str
    source_citations_json: str  # JSON serialized
    analysis_timestamp: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now())
