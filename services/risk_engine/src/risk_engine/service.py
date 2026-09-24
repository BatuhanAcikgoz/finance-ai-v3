"""Risk Engine main service logic."""
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import asyncpg
import numpy as np
import structlog
from redis.asyncio import Redis

from risk_engine.config import settings
from risk_engine.models import RiskAlert, RiskAssessment

logger = structlog.get_logger(__name__)


class RiskEngineService:
    """Service for computing portfolio risk metrics."""

    def __init__(self) -> None:
        """Initialize risk engine service."""
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

    def _check_idempotency(self, portfolio_id: str) -> str:
        """Generate idempotency key for risk assessment."""
        return f"risk:{hashlib.sha256(portfolio_id.encode()).hexdigest()[:16]}"

    async def _is_duplicate(self, idempotency_key: str) -> bool:
        """Check if this assessment was already run today."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        return await self._redis.exists(idempotency_key) > 0

    async def _mark_processed(self, idempotency_key: str) -> None:
        """Mark assessment as processed in Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        await self._redis.setex(idempotency_key, settings.idempotency_key_ttl_seconds, "1")

    async def _fetch_portfolio_holdings(self, portfolio_id: str) -> list[dict[str, Any]]:
        """Fetch current portfolio holdings."""
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
            return [dict(row) for row in rows]

    async def _fetch_returns(
        self, tickers: list[str], days: int
    ) -> dict[str, list[float]]:
        """Fetch historical returns for tickers."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        returns = {}
        async with self._pool.acquire() as conn:
            for ticker in tickers:
                rows = await conn.fetch(
                    """
                    SELECT close
                    FROM market_data.bars
                    WHERE ticker = $1 AND timeframe = '1d'
                    ORDER BY date DESC
                    LIMIT $2
                    """,
                    ticker,
                    days,
                )
                if len(rows) >= 2:
                    prices = [r["close"] for r in reversed(rows)]
                    ticker_returns = np.diff(prices) / prices[:-1]
                    returns[ticker] = ticker_returns.tolist()
        return returns

    def _compute_var(self, returns: np.ndarray, alpha: float = 0.95) -> float:
        """Compute Value at Risk using historical simulation."""
        if len(returns) < 2:
            return 0.0
        return float(np.percentile(returns, (1 - alpha) * 100))

    def _compute_cvar(self, returns: np.ndarray, alpha: float = 0.95) -> float:
        """Compute Conditional VaR (Expected Shortfall)."""
        var = self._compute_var(returns, alpha)
        tail = returns[returns <= var]
        return float(tail.mean()) if len(tail) > 0 else var

    def _compute_beta(
        self, port_returns: np.ndarray, bench_returns: np.ndarray
    ) -> float:
        """Compute portfolio beta to BIST-100."""
        if len(port_returns) < 2 or len(bench_returns) < 2:
            return 1.0
        min_len = min(len(port_returns), len(bench_returns))
        port = port_returns[-min_len:]
        bench = bench_returns[-min_len:]
        cov = np.cov(port, bench)
        if cov[1, 1] == 0:
            return 1.0
        return float(cov[0, 1] / cov[1, 1])

    def _compute_tracking_error(
        self, port_returns: np.ndarray, bench_returns: np.ndarray
    ) -> float:
        """Compute annualized tracking error."""
        if len(port_returns) < 2 or len(bench_returns) < 2:
            return 0.0
        min_len = min(len(port_returns), len(bench_returns))
        excess = port_returns[-min_len:] - bench_returns[-min_len:]
        return float(excess.std() * np.sqrt(252))

    def _compute_hhi(self, weights: np.ndarray) -> float:
        """Compute Herfindahl-Hirschman Index of concentration."""
        return float((weights**2).sum())

    def _compute_sharpe(
        self, returns: np.ndarray, rf: float = 0.0, periods: int = 252
    ) -> float:
        """Compute Sharpe ratio."""
        if len(returns) < 2:
            return 0.0
        excess = returns - rf / periods
        if excess.std() == 0:
            return 0.0
        return float(np.sqrt(periods) * excess.mean() / excess.std())

    def _compute_sortino(
        self, returns: np.ndarray, rf: float = 0.0, periods: int = 252
    ) -> float:
        """Compute Sortino ratio."""
        if len(returns) < 2:
            return 0.0
        excess = returns - rf / periods
        downside = excess[excess < 0]
        if len(downside) == 0 or downside.std() == 0:
            return 0.0
        return float(np.sqrt(periods) * excess.mean() / downside.std())

    def _compute_max_drawdown(self, returns: np.ndarray) -> float:
        """Compute maximum drawdown."""
        if len(returns) < 2:
            return 0.0
        cumulative = np.cumprod(1 + returns)
        peak = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - peak) / peak
        return float(drawdown.min())

    async def _fetch_sector_for_ticker(self, ticker: str) -> str | None:
        """Fetch sector for a ticker."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT sector_index FROM market_data.constituents
                WHERE ticker = $1
                """,
                ticker,
            )
            return row["sector_index"] if row else None

    async def _compute_sector_exposures(
        self, holdings: list[dict[str, Any]]
    ) -> dict[str, float]:
        """Compute sector exposures from holdings."""
        sector_values: dict[str, float] = {}
        total_value = sum(h["current_value_try"] for h in holdings)

        for h in holdings:
            sector = await self._fetch_sector_for_ticker(h["ticker"]) or "UNKNOWN"
            sector_values[sector] = sector_values.get(sector, 0) + h["current_value_try"]

        # Convert to weights
        if total_value > 0:
            return {k: v / total_value for k, v in sector_values.items()}
        return {}

    async def _insert_risk_assessment(self, assessment: RiskAssessment) -> None:
        """Insert risk assessment into PostgreSQL."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO risk.risk_assessments
                (assessment_id, portfolio_id, as_of_date, var_1d_95, cvar_1d_95,
                 beta_to_bist100, tracking_error_1y, hhi_concentration, sector_exposures,
                 risk_budget_pct, risk_budget_exceeded, sharpe_ratio, sortino_ratio,
                 max_drawdown, data_completeness)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                """,
                assessment.assessment_id,
                assessment.portfolio_id,
                assessment.as_of_date,
                assessment.var_1d_95,
                assessment.cvar_1d_95,
                assessment.beta_to_bist100,
                assessment.tracking_error_1y,
                assessment.hhi_concentration,
                json.dumps(assessment.sector_exposures),
                assessment.risk_budget_pct,
                assessment.risk_budget_exceeded,
                assessment.sharpe_ratio,
                assessment.sortino_ratio,
                assessment.max_drawdown,
                assessment.data_completeness,
            )

    async def _emit_alert(self, alert: RiskAlert) -> None:
        """Emit risk alert to Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        await self._redis.publish("risk.alert", alert.model_dump_json())

    async def assess_portfolio(
        self, portfolio_id: str
    ) -> tuple[RiskAssessment, list[RiskAlert]]:
        """
        Run full risk assessment for a portfolio.

        Returns:
            Tuple of (RiskAssessment, list of RiskAlerts if any thresholds breached)
        """
        today_iso = datetime.now(UTC).date().isoformat()
        idempotency_key = self._check_idempotency(f"{portfolio_id}:{today_iso}")

        if await self._is_duplicate(idempotency_key):
            logger.info("risk_assessment_already_run_today", portfolio_id=portfolio_id)
            cached = await self._redis.get(f"risk:result:{idempotency_key}")
            if cached:
                data = json.loads(cached)
                return RiskAssessment(**data["assessment"]), [
                    RiskAlert(**a) for a in data.get("alerts", [])
                ]

        await self.initialize()

        try:
            # Fetch holdings
            holdings = await self._fetch_portfolio_holdings(portfolio_id)
            if not holdings:
                return RiskAssessment(
                    assessment_id=f"empty_{portfolio_id}_{today_iso}",
                    portfolio_id=portfolio_id,
                    as_of_date=datetime.now(UTC).isoformat(),
                    var_1d_95=0.0,
                    cvar_1d_95=0.0,
                    beta_to_bist100=1.0,
                    hhi_concentration=0.0,
                    risk_budget_exceeded=False,
                    data_completeness="missing",
                ), []

            # Get tickers
            tickers = [h["ticker"] for h in holdings]
            weights = np.array([h["current_weight"] for h in holdings])

            # Fetch returns
            returns_data = await self._fetch_returns(tickers, settings.lookback_days)
            bench_returns = await self._fetch_returns(["XU100"], settings.lookback_days)

            # Compute portfolio returns (weighted)
            port_returns_list: list[float] = []
            if returns_data:
                min_len = min(len(r) for r in returns_data.values()) if returns_data else 0
                if min_len > 0:
                    weighted_returns = np.zeros(min_len)
                    for i, ticker in enumerate(tickers):
                        if ticker in returns_data and len(returns_data[ticker]) >= min_len:
                            weighted_returns += weights[i] * np.array(returns_data[ticker][:min_len])
                    port_returns_list = weighted_returns.tolist()

            port_returns = np.array(port_returns_list) if port_returns_list else np.array([0.0])
            bench_arr = (
                np.array(bench_returns.get("XU100", [0.0]))
                if bench_returns
                else np.array([0.0])
            )

            # Compute risk metrics
            var_1d_95 = self._compute_var(port_returns, settings.var_confidence)
            cvar_1d_95 = self._compute_cvar(port_returns, settings.var_confidence)
            beta = self._compute_beta(port_returns, bench_arr)
            tracking_error = self._compute_tracking_error(port_returns, bench_arr)
            hhi = self._compute_hhi(weights)
            sharpe = self._compute_sharpe(port_returns)
            sortino = self._compute_sortino(port_returns)
            max_dd = self._compute_max_drawdown(port_returns)

            # Compute sector exposures
            sector_exposures = await self._compute_sector_exposures(holdings)

            # Check risk budget
            risk_budget_exceeded = abs(var_1d_95) > settings.max_portfolio_var_pct

            # Build assessment
            assessment = RiskAssessment(
                assessment_id=f"risk_{portfolio_id}_{today_iso}",
                portfolio_id=portfolio_id,
                as_of_date=datetime.now(UTC).isoformat(),
                var_1d_95=var_1d_95,
                cvar_1d_95=cvar_1d_95,
                beta_to_bist100=beta,
                tracking_error_1y=tracking_error,
                hhi_concentration=hhi,
                sector_exposures=sector_exposures,
                risk_budget_pct=settings.max_portfolio_var_pct,
                risk_budget_exceeded=risk_budget_exceeded,
                sharpe_ratio=sharpe,
                sortino_ratio=sortino,
                max_drawdown=max_dd,
                data_completeness="complete" if len(holdings) >= 5 else "partial",
            )

            # Generate alerts
            alerts: list[RiskAlert] = []

            if abs(var_1d_95) > settings.var_critical_threshold:
                alerts.append(
                    RiskAlert(
                        portfolio_id=portfolio_id,
                        alert_type="VAR_CRITICAL",
                        severity="CRITICAL",
                        message=f"VaR {abs(var_1d_95)*100:.1f}% exceeds critical threshold {settings.var_critical_threshold*100:.1f}%",
                        metric_value=var_1d_95,
                        threshold=settings.var_critical_threshold,
                    )
                )
            elif abs(var_1d_95) > settings.var_warning_threshold:
                alerts.append(
                    RiskAlert(
                        portfolio_id=portfolio_id,
                        alert_type="VAR_WARNING",
                        severity="WARNING",
                        message=f"VaR {abs(var_1d_95)*100:.1f}% exceeds warning threshold {settings.var_warning_threshold*100:.1f}%",
                        metric_value=var_1d_95,
                        threshold=settings.var_warning_threshold,
                    )
                )

            if hhi > settings.concentration_critical_hhi:
                alerts.append(
                    RiskAlert(
                        portfolio_id=portfolio_id,
                        alert_type="CONCENTRATION_CRITICAL",
                        severity="CRITICAL",
                        message=f"HHI {hhi:.3f} indicates highly concentrated portfolio",
                        metric_value=hhi,
                        threshold=settings.concentration_critical_hhi,
                    )
                )
            elif hhi > settings.concentration_warning_hhi:
                alerts.append(
                    RiskAlert(
                        portfolio_id=portfolio_id,
                        alert_type="CONCENTRATION_WARNING",
                        severity="WARNING",
                        message=f"HHI {hhi:.3f} indicates concentrated portfolio",
                        metric_value=hhi,
                        threshold=settings.concentration_warning_hhi,
                    )
                )

            if abs(beta - 1.0) > settings.max_beta - 1.0:
                alerts.append(
                    RiskAlert(
                        portfolio_id=portfolio_id,
                        alert_type="BETA_EXCEEDED",
                        severity="WARNING",
                        message=f"Beta {beta:.2f} exceeds max allowed {settings.max_beta:.2f}",
                        metric_value=beta,
                        threshold=settings.max_beta,
                    )
                )

            # Check sector concentration
            for sector, exposure in sector_exposures.items():
                if exposure > settings.max_sector_pct:
                    alerts.append(
                        RiskAlert(
                            portfolio_id=portfolio_id,
                            alert_type="SECTOR_CONCENTRATION",
                            severity="WARNING",
                            message=f"Sector {sector} exposure {exposure*100:.1f}% exceeds max {settings.max_sector_pct*100:.1f}%",
                            metric_value=exposure,
                            threshold=settings.max_sector_pct,
                        )
                    )

            # Store assessment
            await self._insert_risk_assessment(assessment)

            # Emit alerts
            for alert in alerts:
                await self._emit_alert(alert)

            # Cache result
            if self._redis:
                cache_data = {
                    "assessment": assessment.model_dump(mode="json"),
                    "alerts": [a.model_dump(mode="json") for a in alerts],
                }
                await self._redis.setex(f"risk:result:{idempotency_key}", 3600, json.dumps(cache_data, default=str))

            await self._mark_processed(idempotency_key)

            logger.info(
                "risk_assessment_complete",
                portfolio_id=portfolio_id,
                var=var_1d_95,
                cvar=cvar_1d_95,
                hhi=hhi,
                alerts=len(alerts),
            )

            return assessment, alerts

        finally:
            await self.close()

    async def run(self) -> None:
        """Run the risk engine as a scheduled job."""
        logger.info("risk_engine_service_started")
        while True:
            now = datetime.now(UTC)
            # Run daily at 19:00 TRT (16:00 UTC) - after market close
            if now.hour == 16 and now.minute >= 0:
                try:
                    # Get all active portfolios
                    if self._pool is None:
                        await self.initialize()

                    async with self._pool.acquire() as conn:
                        rows = await conn.fetch("SELECT portfolio_id FROM portfolio.portfolios WHERE active = true")
                        for row in rows:
                            try:
                                await self.assess_portfolio(row["portfolio_id"])
                            except Exception as e:
                                logger.error("portfolio_risk_failed", portfolio_id=row["portfolio_id"], error=str(e))
                except Exception as e:
                    logger.error("daily_risk_run_failed", error=str(e))

            import asyncio
            await asyncio.sleep(300)  # Check every 5 minutes
