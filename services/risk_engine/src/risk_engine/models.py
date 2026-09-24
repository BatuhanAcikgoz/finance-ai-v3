"""Risk Engine Pydantic models."""
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class RiskAssessment(BaseModel):
    """Complete risk assessment for a portfolio."""

    assessment_id: str = Field(default_factory=lambda: str(uuid4()))
    portfolio_id: str
    as_of_date: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    # VaR metrics
    var_1d_95: float = Field(..., description="1-day 95% VaR as decimal (negative = loss)")
    cvar_1d_95: float = Field(..., description="1-day 95% CVaR (Expected Shortfall)")

    # Beta and tracking
    beta_to_bist100: float = Field(..., description="Portfolio beta to BIST-100")
    tracking_error_1y: float = Field(0.0, description="Annualized tracking error")

    # Concentration
    hhi_concentration: float = Field(..., ge=0.0, le=1.0, description="HHI concentration index")

    # Sector exposures
    sector_exposures: dict[str, float] = Field(default_factory=dict)

    # Style exposures
    style_exposures: dict[str, float] = Field(default_factory=dict)

    # Risk budget status
    risk_budget_pct: float = 0.03
    risk_budget_exceeded: bool = False

    # Additional metrics
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    max_drawdown: float | None = None

    data_completeness: str = Field("complete", pattern="^(complete|partial|missing)$")


class Holding(BaseModel):
    """Single portfolio holding."""

    ticker: str
    shares: float = Field(..., ge=0)
    current_price: float = Field(..., ge=0)
    current_value_try: float = Field(..., ge=0)
    current_weight: float = Field(..., ge=0.0, le=1.0)
    target_weight: float = Field(0.0, ge=0.0, le=1.0)
    cost_basis_try: float = 0.0
    unrealized_pnl_try: float = 0.0


class PortfolioRiskSnapshot(BaseModel):
    """Portfolio risk snapshot at a point in time."""

    portfolio_id: str
    as_of: str
    total_value_try: float = Field(..., ge=0)
    holdings: list[Holding]

    # Computed risk metrics
    var_1d_95: float = 0.0
    cvar_1d_95: float = 0.0
    beta: float = 1.0
    hhi: float = 0.0
    sector_concentration: dict[str, float] = Field(default_factory=dict)

    # Constraints check
    constraints_violated: list[str] = Field(default_factory=list)


class RiskAlert(BaseModel):
    """Risk alert generated when thresholds are breached."""

    alert_id: str = Field(default_factory=lambda: str(uuid4()))
    portfolio_id: str
    ticker: str | None = None  # None means portfolio-level alert
    alert_type: str  # VAR_BREACH, CONCENTRATION, BETA_EXCEEDED, etc.
    severity: str  # WARNING, CRITICAL, EMERGENCY
    message: str
    metric_value: float
    threshold: float
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
