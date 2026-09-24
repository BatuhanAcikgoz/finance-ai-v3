"""Portfolio endpoint tests — uses monkeypatched db helpers, no Postgres."""

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

import db
import main as main_module


@pytest.fixture
async def client():
    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class _Row(dict):
    """Dict that supports attribute-style access — mimics asyncpg.Record."""

    def __getitem__(self, k):
        return dict.__getitem__(self, k)


def _row(items):
    return [_Row(d) for d in items]


def make_async_return(value):
    async def _fn(*a, **kw):
        return value
    return _fn


def make_async_iter(values):
    iterator = iter(values)

    async def _fn(*a, **kw):
        return next(iterator)
    return _fn


PORTFOLIO_UUID = "11111111-1111-1111-1111-111111111111"
NOW = datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc)


async def test_list_portfolios_returns_rows(client, monkeypatch):
    canned = _row([
        {
            "portfolio_id": PORTFOLIO_UUID,
            "user_id": PORTFOLIO_UUID,
            "name": "Growth",
            "base_currency": "TRY",
            "risk_budget_pct": 0.03,
            "max_position_pct": 0.25,
            "max_sector_pct": 0.40,
            "created_at": NOW,
            "updated_at": NOW,
        },
    ])
    monkeypatch.setattr(db, "fetch", make_async_return(canned))
    monkeypatch.setattr(db, "is_available", make_async_return(True))

    r = await client.get("/v1/portfolio/")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["items"][0]["name"] == "Growth"
    assert body["items"][0]["base_currency"] == "TRY"


async def test_list_portfolios_synthesizes_default_when_empty(client, monkeypatch):
    monkeypatch.setattr(db, "fetch", make_async_return([]))
    monkeypatch.setattr(db, "is_available", make_async_return(True))

    r = await client.get("/v1/portfolio/")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["items"][0]["portfolio_id"] == "default"
    assert body["items"][0].get("synthesized") is True


async def test_get_portfolio_state_aggregates(client, monkeypatch):
    portfolio_row = _Row({
        "portfolio_id": PORTFOLIO_UUID,
        "user_id": PORTFOLIO_UUID,
        "name": "Growth",
        "base_currency": "TRY",
        "risk_budget_pct": 0.03,
        "max_position_pct": 0.25,
        "max_sector_pct": 0.40,
        "created_at": NOW,
        "updated_at": NOW,
    })
    holdings = _row([
        {
            "ticker": "THYAO",
            "shares": 100,
            "cost_basis_try": 50.0,
            "target_weight": 0.6,
            "current_price": 80.0,
            "current_value": 8000.0,
            "unrealized_pnl": 3000.0,
            "updated_at": NOW,
            "ticker_name": "Turk Hava Yollari",
        },
        {
            "ticker": "GARAN",
            "shares": 50,
            "cost_basis_try": 40.0,
            "target_weight": 0.4,
            "current_price": 60.0,
            "current_value": 3000.0,
            "unrealized_pnl": 1000.0,
            "updated_at": NOW,
            "ticker_name": "Garanti BBVA",
        },
    ])

    # fetchrow is called once (portfolio), fetch once (holdings),
    # is_available once for the degraded check.
    monkeypatch.setattr(db, "fetchrow", make_async_return(portfolio_row))
    monkeypatch.setattr(db, "fetch", make_async_return(holdings))
    monkeypatch.setattr(db, "is_available", make_async_return(True))

    r = await client.get(f"/v1/portfolio/{PORTFOLIO_UUID}/state")
    assert r.status_code == 200
    body = r.json()
    assert body["total_value_try"] == 11000.0
    assert body["portfolio"]["name"] == "Growth"
    assert len(body["holdings"]) == 2
    # Total cost = (50*100) + (40*50) = 5000 + 2000 = 7000
    assert body["total_cost_try"] == 7000.0
    # Unrealized = 11000 - 7000 = 4000
    assert body["unrealized_pnl_try"] == 4000.0
    # Both holdings have weights ≠ targets, so drift HHI > 0.
    # THYAO weight = 8000/11000 ≈ 0.7273 vs target 0.6 → drift ≈ 0.1273
    # GARAN weight = 3000/11000 ≈ 0.2727 vs target 0.4  → drift ≈ -0.1273
    # HHI = 0.1273^2 + (-0.1273)^2 ≈ 0.0324
    assert body["weights_drift_hhi"] == pytest.approx(0.0324, abs=1e-3)


async def test_get_holding_returns_decisions_and_risk(client, monkeypatch):
    holding_row = _Row({
        "ticker": "THYAO",
        "shares": 100,
        "cost_basis_try": 50.0,
        "target_weight": 0.5,
        "current_price": 80.0,
        "current_value": 8000.0,
        "unrealized_pnl": 3000.0,
        "updated_at": NOW,
        "ticker_name": "Turk Hava Yollari",
    })
    decision_rows = _row([
        {
            "decision_id": "22222222-2222-2222-2222-222222222222",
            "action": "BUY",
            "confidence": 0.85,
            "effective_at": NOW,
        },
    ])

    # fetchrow → holding, fetch → decisions
    monkeypatch.setattr(db, "fetchrow", make_async_return(holding_row))
    monkeypatch.setattr(db, "fetch", make_async_return(decision_rows))
    monkeypatch.setattr(db, "is_available", make_async_return(True))

    r = await client.get(f"/v1/portfolio/{PORTFOLIO_UUID}/holdings/THYAO")
    assert r.status_code == 200
    body = r.json()
    assert body["holding"]["ticker"] == "THYAO"
    assert body["holding"]["quantity"] == 100
    assert len(body["recent_decisions"]) == 1
    assert body["recent_decisions"][0]["action"] == "BUY"
    # Risk metrics are placeholders for v1 (not stored on holdings).
    assert body["risk_metrics"]["beta"] is None
    assert body["risk_metrics"]["var_95_1d_pct"] is None
