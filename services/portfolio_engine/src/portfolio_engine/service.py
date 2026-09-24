"""Portfolio Engine main service logic."""
import json
from datetime import UTC, datetime
from typing import Any

import asyncpg
import structlog
from redis.asyncio import Redis

from portfolio_engine.config import settings
from portfolio_engine.models import (
    Holding,
    Order,
    OrderSide,
    OrderStatus,
    PortfolioState,
    RebalanceRecommendation,
    Trade,
)

logger = structlog.get_logger(__name__)


class PortfolioEngineService:
    """Service for managing portfolio state and executing trades."""

    def __init__(self) -> None:
        """Initialize portfolio engine service."""
        self._redis: Redis | None = None
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        """Initialize Redis and database connections."""
        self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        self._pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)

    async def close(self) -> None:
        """Close all connections."""
        if self._redis:
            await self._redis.close()
        if self._pool:
            await self._pool.close()

    def _is_trading_hours(self) -> bool:
        """Check if currently within trading hours (TRT)."""
        now = datetime.now(UTC)
        # TRT is UTC+3
        trt_hour = (now.hour + 3) % 24
        return settings.trading_start_hour <= trt_hour < settings.trading_end_hour

    async def _fetch_holdings(self, portfolio_id: str) -> list[Holding]:
        """Fetch current holdings for a portfolio."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT ticker, shares, current_price, current_value_try,
                       current_weight, target_weight, cost_basis_try, unrealized_pnl_try
                FROM portfolio.holdings
                WHERE portfolio_id = $1 AND shares > 0
                """,
                portfolio_id,
            )

            holdings = []
            for row in rows:
                cost = row["cost_basis_try"] or 0
                pnl = row["unrealized_pnl_try"] or 0
                pnl_pct = (pnl / cost) if cost > 0 else 0.0

                holdings.append(
                    Holding(
                        ticker=row["ticker"],
                        shares=row["shares"],
                        current_price=row["current_price"],
                        current_value_try=row["current_value_try"],
                        current_weight=row["current_weight"],
                        target_weight=row["target_weight"] or 0.0,
                        cost_basis_try=cost,
                        unrealized_pnl_try=pnl,
                        unrealized_pnl_pct=pnl_pct,
                    )
                )
            return holdings

    async def _fetch_portfolio(self, portfolio_id: str) -> dict[str, Any] | None:
        """Fetch portfolio metadata."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT portfolio_id, user_id, total_value_try, cash_try
                FROM portfolio.portfolios
                WHERE portfolio_id = $1
                """,
                portfolio_id,
            )
            return dict(row) if row else None

    async def _get_current_price(self, ticker: str) -> float | None:
        """Get current market price for a ticker."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT close
                FROM market_data.bars
                WHERE ticker = $1 AND timeframe = '1d'
                ORDER BY date DESC
                LIMIT 1
                """,
                ticker,
            )
            return row["close"] if row else None

    async def _update_holding(
        self,
        portfolio_id: str,
        ticker: str,
        shares: float,
        price: float,
        side: OrderSide,
    ) -> None:
        """Update holding after a trade."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            if side == OrderSide.BUY:
                # Add to position
                await conn.execute(
                    """
                    INSERT INTO portfolio.holdings
                    (portfolio_id, ticker, shares, current_price, current_value_try,
                     current_weight, target_weight, cost_basis_try, unrealized_pnl_try)
                    VALUES ($1, $2, $3, $4, $5, $6, 0, $7, 0)
                    ON CONFLICT (portfolio_id, ticker) DO UPDATE SET
                        shares = portfolio.holdings.shares + EXCLUDED.shares,
                        current_price = EXCLUDED.current_price,
                        current_value_try = (portfolio.holdings.shares + EXCLUDED.shares) * EXCLUDED.current_price,
                        cost_basis_try = portfolio.holdings.cost_basis_try + EXCLUDED.current_price * EXCLUDED.shares
                    """,
                    portfolio_id,
                    ticker,
                    shares,
                    price,
                    shares * price,
                    shares * price,
                    shares * price,
                )
            else:
                # Reduce position
                await conn.execute(
                    """
                    UPDATE portfolio.holdings
                    SET shares = GREATEST(0, shares - $3),
                        current_price = $4,
                        current_value_try = GREATEST(0, shares - $3) * $4
                    WHERE portfolio_id = $1 AND ticker = $2
                    """,
                    portfolio_id,
                    ticker,
                    shares,
                    price,
                )

    async def _insert_trade(self, trade: Trade) -> None:
        """Insert trade record into database."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO portfolio.trades
                (trade_id, order_id, portfolio_id, ticker, side, shares, price,
                 value_try, commission_try, executed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                trade.trade_id,
                trade.order_id,
                trade.portfolio_id,
                trade.ticker,
                trade.side.value,
                trade.shares,
                trade.price,
                trade.value_try,
                trade.commission_try,
                trade.executed_at,
            )

    async def get_portfolio_state(self, portfolio_id: str) -> PortfolioState:
        """Get current portfolio state."""
        portfolio = await self._fetch_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        holdings = await self._fetch_holdings(portfolio_id)

        return PortfolioState(
            portfolio_id=portfolio_id,
            user_id=portfolio["user_id"],
            total_value_try=portfolio["total_value_try"],
            cash_try=portfolio["cash_try"] or 0.0,
            holdings=holdings,
        )

    async def submit_order(self, order: Order) -> Order:
        """Submit a trading order."""
        if not self._is_trading_hours():
            order.status = OrderStatus.REJECTED
            logger.warning("order_rejected_outside_hours", order_id=order.order_id)
            return order

        # Get current price
        price = order.limit_price or await self._get_current_price(order.ticker)
        if not price:
            order.status = OrderStatus.REJECTED
            logger.warning("order_rejected_no_price", ticker=order.ticker)
            return order

        # Validate order value
        order_value = order.shares * price
        if order_value < settings.min_trade_value_try:
            order.status = OrderStatus.REJECTED
            logger.warning("order_rejected_too_small", order_value=order_value)
            return order
        if order_value > settings.max_trade_value_try:
            order.status = OrderStatus.REJECTED
            logger.warning("order_rejected_too_large", order_value=order_value)
            return order

        order.status = OrderStatus.SUBMITTED

        # Execute immediately (simplified - in production would go to broker)
        try:
            # Create trade
            trade = Trade(
                order_id=order.order_id,
                portfolio_id=order.portfolio_id,
                ticker=order.ticker,
                side=order.side,
                shares=order.shares,
                price=price,
                value_try=order.shares * price,
            )

            # Update holding
            await self._update_holding(order.portfolio_id, order.ticker, order.shares, price, order.side)

            # Insert trade record
            await self._insert_trade(trade)

            order.status = OrderStatus.FILLED
            logger.info(
                "order_filled",
                order_id=order.order_id,
                ticker=order.ticker,
                side=order.side.value,
                shares=order.shares,
                price=price,
            )

            # Emit event
            if self._redis:
                await self._redis.publish(
                    "trade.executed",
                    json.dumps(
                        {
                            "event_type": "trade.executed",
                            "trade_id": trade.trade_id,
                            "portfolio_id": order.portfolio_id,
                            "ticker": order.ticker,
                            "side": order.side.value,
                            "shares": order.shares,
                            "price": price,
                            "timestamp": trade.executed_at,
                        }
                    ),
                )

        except Exception as e:
            order.status = OrderStatus.REJECTED
            logger.error("order_execution_failed", order_id=order.order_id, error=str(e))

        return order

    async def get_rebalance_recommendations(
        self, portfolio_id: str
    ) -> list[RebalanceRecommendation]:
        """Get rebalancing recommendations for a portfolio."""
        holdings = await self._fetch_holdings(portfolio_id)
        recommendations = []

        for h in holdings:
            drift = abs(h.current_weight - h.target_weight)
            if drift > settings.rebalance_threshold_pct:
                action = OrderSide.SELL if h.current_weight > h.target_weight else OrderSide.BUY
                shares = abs(h.current_weight - h.target_weight) * h.current_value_try / h.current_price

                recommendations.append(
                    RebalanceRecommendation(
                        portfolio_id=portfolio_id,
                        ticker=h.ticker,
                        current_weight=h.current_weight,
                        target_weight=h.target_weight,
                        drift_pct=drift,
                        action=action,
                        estimated_shares=shares,
                        estimated_value_try=abs(h.current_weight - h.target_weight) * h.current_value_try,
                        priority=int(drift * 100),  # Higher drift = higher priority
                    )
                )

        # Sort by priority (highest first)
        recommendations.sort(key=lambda r: r.priority, reverse=True)
        return recommendations

    async def run(self) -> None:
        """Run the portfolio engine as a background service."""
        logger.info("portfolio_engine_service_started")
        while True:
            # Check for pending orders and execute them
            # In production, this would poll a broker API or listen for events
            import asyncio
            await asyncio.sleep(60)  # Check every minute
