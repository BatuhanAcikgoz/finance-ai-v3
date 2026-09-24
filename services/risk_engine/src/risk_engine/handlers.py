"""FastAPI handlers for Risk Engine service."""
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from risk_engine.models import RiskAlert, RiskAssessment
from risk_engine.service import RiskEngineService

router = APIRouter(prefix="/risk", tags=["risk"])


class AssessPortfolioResponse(BaseModel):
    """Response from risk assessment."""

    assessment: RiskAssessment
    alerts: list[RiskAlert]
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class RiskMetricResponse(BaseModel):
    """Response for specific risk metric."""

    portfolio_id: str
    metric_name: str
    metric_value: float
    threshold: float | None = None
    status: str  # OK, WARNING, CRITICAL


# Service instance
_service: RiskEngineService | None = None


def get_service() -> RiskEngineService:
    """Get or create service instance."""
    global _service
    if _service is None:
        _service = RiskEngineService()
    return _service


@router.post("/assess/{portfolio_id}", response_model=AssessPortfolioResponse)
async def assess_portfolio(portfolio_id: str) -> AssessPortfolioResponse:
    """
    Run full risk assessment for a portfolio.

    Computes VaR, CVaR, beta, HHI, sector exposures, and generates alerts
    if any risk thresholds are breached.
    """
    service = get_service()

    try:
        assessment, alerts = await service.assess_portfolio(portfolio_id)

        return AssessPortfolioResponse(assessment=assessment, alerts=alerts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk assessment failed: {e!s}")


@router.get("/var/{portfolio_id}")
async def get_var(portfolio_id: str) -> RiskMetricResponse:
    """Get VaR metric for a portfolio."""
    service = get_service()

    try:
        assessment, alerts = await service.assess_portfolio(portfolio_id)

        var_alert = next((a for a in alerts if "VAR" in a.alert_type), None)
        if var_alert:
            status = var_alert.severity
        else:
            status = "OK"

        return RiskMetricResponse(
            portfolio_id=portfolio_id,
            metric_name="var_1d_95",
            metric_value=assessment.var_1d_95,
            threshold=assessment.risk_budget_pct,
            status=status,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch VaR: {e!s}")


@router.get("/hhi/{portfolio_id}")
async def get_hhi(portfolio_id: str) -> RiskMetricResponse:
    """Get HHI concentration metric for a portfolio."""
    service = get_service()

    try:
        assessment, alerts = await service.assess_portfolio(portfolio_id)

        hhi_alert = next((a for a in alerts if "CONCENTRATION" in a.alert_type), None)
        if hhi_alert:
            status = hhi_alert.severity
        else:
            status = "OK"

        return RiskMetricResponse(
            portfolio_id=portfolio_id,
            metric_name="hhi_concentration",
            metric_value=assessment.hhi_concentration,
            threshold=0.25,  # Warning threshold
            status=status,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch HHI: {e!s}")


@router.get("/beta/{portfolio_id}")
async def get_beta(portfolio_id: str) -> RiskMetricResponse:
    """Get beta to BIST-100 for a portfolio."""
    service = get_service()

    try:
        assessment, alerts = await service.assess_portfolio(portfolio_id)

        beta_alert = next((a for a in alerts if "BETA" in a.alert_type), None)
        if beta_alert:
            status = beta_alert.severity
        else:
            status = "OK"

        return RiskMetricResponse(
            portfolio_id=portfolio_id,
            metric_name="beta_to_bist100",
            metric_value=assessment.beta_to_bist100,
            threshold=1.5,
            status=status,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch beta: {e!s}")


@router.get("/sector-exposures/{portfolio_id}")
async def get_sector_exposures(portfolio_id: str) -> dict[str, Any]:
    """Get sector exposures for a portfolio."""
    service = get_service()

    try:
        assessment, _ = await service.assess_portfolio(portfolio_id)
        return {
            "portfolio_id": portfolio_id,
            "sector_exposures": assessment.sector_exposures,
            "max_allowed": 0.40,
            "warnings": [
                {"sector": sector, "exposure": exposure}
                for sector, exposure in assessment.sector_exposures.items()
                if exposure > 0.40
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sector exposures: {e!s}")


@router.get("/history/{portfolio_id}")
async def get_risk_history(
    portfolio_id: str, limit: int = 30
) -> list[RiskAssessment]:
    """Get historical risk assessments for a portfolio."""
    service = get_service()

    try:
        async with service._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT assessment_id, portfolio_id, as_of_date, var_1d_95, cvar_1d_95,
                       beta_to_bist100, tracking_error_1y, hhi_concentration, sector_exposures,
                       risk_budget_pct, risk_budget_exceeded, sharpe_ratio, sortino_ratio,
                       max_drawdown, data_completeness
                FROM risk.risk_assessments
                WHERE portfolio_id = $1
                ORDER BY as_of_date DESC
                LIMIT $2
                """,
                portfolio_id,
                limit,
            )

            return [
                RiskAssessment(
                    assessment_id=row["assessment_id"],
                    portfolio_id=row["portfolio_id"],
                    as_of_date=row["as_of_date"].isoformat() if row["as_of_date"] else "",
                    var_1d_95=row["var_1d_95"],
                    cvar_1d_95=row["cvar_1d_95"],
                    beta_to_bist100=row["beta_to_bist100"],
                    tracking_error_1y=row["tracking_error_1y"],
                    hhi_concentration=row["hhi_concentration"],
                    sector_exposures=json.loads(row["sector_exposures"]) if row["sector_exposures"] else {},
                    risk_budget_pct=row["risk_budget_pct"],
                    risk_budget_exceeded=row["risk_budget_exceeded"],
                    sharpe_ratio=row["sharpe_ratio"],
                    sortino_ratio=row["sortino_ratio"],
                    max_drawdown=row["max_drawdown"],
                    data_completeness=row["data_completeness"],
                )
                for row in rows
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch risk history: {e!s}")


@router.get("/alerts/{portfolio_id}")
async def get_alerts(
    portfolio_id: str, days: int = 7
) -> list[RiskAlert]:
    """Get recent risk alerts for a portfolio."""
    service = get_service()

    try:
        async with service._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT alert_id, portfolio_id, ticker, alert_type, severity, message,
                       metric_value, threshold, generated_at
                FROM risk.risk_alerts
                WHERE portfolio_id = $1 AND generated_at >= NOW() - INTERVAL '%s days'
                ORDER BY generated_at DESC
                """,
                portfolio_id,
                days,
            )

            return [
                RiskAlert(
                    alert_id=row["alert_id"],
                    portfolio_id=row["portfolio_id"],
                    ticker=row["ticker"],
                    alert_type=row["alert_type"],
                    severity=row["severity"],
                    message=row["message"],
                    metric_value=row["metric_value"],
                    threshold=row["threshold"],
                    generated_at=row["generated_at"].isoformat() if row["generated_at"] else "",
                )
                for row in rows
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch alerts: {e!s}")


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "risk_engine"}
