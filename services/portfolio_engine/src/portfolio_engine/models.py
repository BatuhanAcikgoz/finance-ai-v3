"""Portfolio Engine Pydantic models."""
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    """Order execution status."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderSide(str, Enum):
    """Order side."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class Trade(BaseModel):
    """Executed trade record."""

    trade_id: str = Field(default_factory=lambda: str(uuid4()))
    order_id: str
    portfolio_id: str
    ticker: str
    side: OrderSide
    shares: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    value_try: float = Field(..., description="Total trade value in TRY")
    commission_try: float = 0.0
    executed_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class Order(BaseModel):
    """Order request."""

    order_id: str = Field(default_factory=lambda: str(uuid4()))
    portfolio_id: str
    ticker: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    shares: float = Field(..., gt=0)
    limit_price: float | None = None
    stop_price: float | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: OrderStatus = OrderStatus.PENDING


class Holding(BaseModel):
    """Portfolio holding."""

    ticker: str
    shares: float = Field(..., ge=0)
    current_price: float = Field(..., ge=0)
    current_value_try: float = Field(..., ge=0)
    current_weight: float = Field(..., ge=0.0, le=1.0)
    target_weight: float = Field(0.0, ge=0.0, le=1.0)
    cost_basis_try: float = 0.0
    unrealized_pnl_try: float = 0.0
    unrealized_pnl_pct: float = 0.0


class PortfolioState(BaseModel):
    """Current portfolio state."""

    portfolio_id: str
    user_id: str
    as_of: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    total_value_try: float = Field(..., ge=0)
    cash_try: float = 0.0
    holdings: list[Holding] = Field(default_factory=list)
    day_pnl_try: float = 0.0
    day_pnl_pct: float = 0.0
    total_pnl_try: float = 0.0
    total_pnl_pct: float = 0.0


class RebalanceRecommendation(BaseModel):
    """Rebalancing recommendation."""

    portfolio_id: str
    ticker: str
    current_weight: float
    target_weight: float
    drift_pct: float
    action: OrderSide
    estimated_shares: float
    estimated_value_try: float
    priority: int = Field(0, ge=0)  # Higher = more urgent


class PortfolioConstraints(BaseModel):
    """Portfolio constraints."""

    max_position_pct: float = 0.25
    max_sector_pct: float = 0.40
    max_portfolio_var_pct: float = 0.03
    rebalance_threshold_pct: float = 0.05
