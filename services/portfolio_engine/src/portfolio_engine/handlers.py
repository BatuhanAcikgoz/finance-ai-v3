"""FastAPI handlers for Portfolio Engine service."""
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from portfolio_engine.models import (
    Holding,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    PortfolioState,
    RebalanceRecommendation,
    Trade,
)
from portfolio_engine.service import PortfolioEngineService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class SubmitOrderRequest(BaseModel):
    """Request to submit a trading order."""

    portfolio_id: str
    ticker: str
    side: OrderSide
    shares: float = Field(..., gt=0)
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None


class OrderResponse(BaseModel):
    """Response after order submission."""

    order: Order
    executed_at: str | None = None


# Service instance
_service: PortfolioEngineService | None = None


def get_service() -> PortfolioEngineService:
    """Get or create service instance."""
    global _service
    if _service is None:
        _service = PortfolioEngineService()
    return _service


@router.get("/{portfolio_id}/state", response_model=PortfolioState)
async def get_portfolio_state(portfolio_id: str) -> PortfolioState:
    """Get current portfolio state including holdings and P&L."""
    service = get_service()

    try:
        return await service.get_portfolio_state(portfolio_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch portfolio state: {e!s}")


@router.get("/{portfolio_id}/holdings")
async def get_holdings(portfolio_id: str) -> list[Holding]:
    """Get current holdings for a portfolio."""
    service = get_service()

    try:
        return await service._fetch_holdings(portfolio_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch holdings: {e!s}")


@router.post("/orders/submit", response_model=OrderResponse)
async def submit_order(request: SubmitOrderRequest) -> OrderResponse:
    """Submit a trading order."""
    service = get_service()

    order = Order(
        portfolio_id=request.portfolio_id,
        ticker=request.ticker.upper(),
        side=request.side,
        shares=request.shares,
        order_type=request.order_type,
        limit_price=request.limit_price,
    )

    try:
        executed_order = await service.submit_order(order)
        return OrderResponse(
            order=executed_order,
            executed_at=executed_order.created_at if executed_order.status == OrderStatus.FILLED else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Order submission failed: {e!s}")


@router.get("/{portfolio_id}/rebalance")
async def get_rebalance_recommendations(portfolio_id: str) -> list[RebalanceRecommendation]:
    """Get rebalancing recommendations for a portfolio."""
    service = get_service()

    try:
        return await service.get_rebalance_recommendations(portfolio_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {e!s}")


@router.get("/{portfolio_id}/trades")
async def get_trade_history(
    portfolio_id: str, limit: int = 50
) -> list[Trade]:
    """Get trade history for a portfolio."""
    service = get_service()

    try:
        async with service._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT trade_id, order_id, portfolio_id, ticker, side, shares,
                       price, value_try, commission_try, executed_at
                FROM portfolio.trades
                WHERE portfolio_id = $1
                ORDER BY executed_at DESC
                LIMIT $2
                """,
                portfolio_id,
                limit,
            )

            return [
                Trade(
                    trade_id=row["trade_id"],
                    order_id=row["order_id"],
                    portfolio_id=row["portfolio_id"],
                    ticker=row["ticker"],
                    side=OrderSide(row["side"]),
                    shares=row["shares"],
                    price=row["price"],
                    value_try=row["value_try"],
                    commission_try=row["commission_try"],
                    executed_at=row["executed_at"].isoformat() if row["executed_at"] else "",
                )
                for row in rows
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch trades: {e!s}")


@router.get("/orders/{order_id}")
async def get_order(order_id: str) -> Order:
    """Get status of a specific order."""
    service = get_service()

    try:
        async with service._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT order_id, portfolio_id, ticker, side, order_type, shares,
                       limit_price, stop_price, created_at, status
                FROM portfolio.orders
                WHERE order_id = $1
                """,
                order_id,
            )

            if row is None:
                raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

            return Order(
                order_id=row["order_id"],
                portfolio_id=row["portfolio_id"],
                ticker=row["ticker"],
                side=OrderSide(row["side"]),
                order_type=OrderType(row["order_type"]),
                shares=row["shares"],
                limit_price=row["limit_price"],
                stop_price=row["stop_price"],
                created_at=row["created_at"].isoformat() if row["created_at"] else "",
                status=OrderStatus(row["status"]),
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch order: {e!s}")


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str) -> dict[str, Any]:
    """Cancel a pending order."""
    service = get_service()

    try:
        async with service._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE portfolio.orders
                SET status = 'CANCELLED'
                WHERE order_id = $1 AND status = 'PENDING'
                """,
                order_id,
            )

            if result == "UPDATE 0":
                raise HTTPException(status_code=400, detail="Order cannot be cancelled (not pending)")

            return {
                "order_id": order_id,
                "status": "CANCELLED",
                "cancelled_at": datetime.now(UTC).isoformat(),
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel order: {e!s}")


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "portfolio_engine"}
