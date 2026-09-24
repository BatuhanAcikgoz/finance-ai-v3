"""Events endpoint tests — uses monkeypatched db helpers."""

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
    def __getitem__(self, k):
        return dict.__getitem__(self, k)


def _row(items):
    return [_Row(d) for d in items]


def make_async_return(value):
    async def _fn(*a, **kw):
        return value
    return _fn


NOW = datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc)


async def test_events_merges_decisions_alerts_and_ticks(client, monkeypatch):
    """GET /v1/events should merge decisions + alerts + a synthetic tick per
    active ticker, sorted newest first."""
    decision_rows = _row([
        {"ticker": "THYAO", "action": "BUY",
         "confidence": 0.85, "created_at": NOW},
    ])
    alert_rows = _row([
        {"ticker": "GARAN", "grade": "WARN", "title": "Drawdown breach",
         "created_at": NOW},
    ])
    ticker_rows = _row([
        {"ticker": "THYAO", "name": "Turk Hava Yollari"},
        {"ticker": "GARAN", "name": "Garanti BBVA"},
    ])

    # db.fetch is called 3x — decisions, alerts, tickers. Return them in order.
    iterator = iter([decision_rows, alert_rows, ticker_rows])

    async def fake_fetch(query, *args, **kw):
        return next(iterator)

    monkeypatch.setattr(db, "fetch", fake_fetch)

    r = await client.get("/v1/events/?limit=50")
    assert r.status_code == 200
    body = r.json()
    types = {it["type"] for it in body["items"]}
    # All three event types should appear because we have ≥1 real event
    # (which is the anchor the route uses to decide whether to synthesize ticks).
    assert "decision.created" in types
    assert "alert.new" in types
    assert "market.tick" in types
    # Counts: 1 decision + 1 alert + 2 ticks = 4
    assert body["count"] == 4
    tickers = {it["ticker"] for it in body["items"]}
    assert {"THYAO", "GARAN"} <= tickers
