"""Market endpoint tests — uses monkeypatched canned data, no Postgres required."""

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


# --- helpers: monkeypatched db helpers as ASYNC (production awaits them) ---

def make_async_return(value):
    async def _fn(*a, **kw):
        return value
    return _fn


def make_async_iter(values):
    iterator = iter(values)

    async def _fn(*a, **kw):
        return next(iterator)
    return _fn


async def test_symbols_returns_list(client, monkeypatch):
    canned = _row([
        {"ticker": "THYAO", "name": "Turk Hava Yollari", "sector": "TRANSPORT",
         "subsector": "Airlines", "is_index": False, "is_active": True},
        {"ticker": "GARAN", "name": "Garanti BBVA", "sector": "FINANCIAL",
         "subsector": "Banks", "is_index": False, "is_active": True},
    ])
    monkeypatch.setattr(db, "fetch", make_async_return(canned))
    monkeypatch.setattr(db, "is_available", make_async_return(True))

    r = await client.get("/v1/market/symbols")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert body["items"][0]["ticker"] == "THYAO"


async def test_symbols_degraded_when_db_down(client, monkeypatch):
    monkeypatch.setattr(db, "fetch", make_async_return([]))
    monkeypatch.setattr(db, "is_available", make_async_return(False))

    r = await client.get("/v1/market/symbols")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["degraded"] is True


async def test_ohlcv_returns_bars_desc(client, monkeypatch):
    ts = datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    canned = _row([
        {"ticker": "THYAO", "timeframe": "1d", "open": 100.0, "high": 110.0,
         "low": 99.0, "close": 108.0, "volume": 1000.0,
         "bar_start": ts, "bar_end": ts},
        {"ticker": "THYAO", "timeframe": "1d", "open": 95.0, "high": 102.0,
         "low": 94.0, "close": 100.0, "volume": 800.0,
         "bar_start": ts2, "bar_end": ts2},
    ])
    monkeypatch.setattr(db, "fetch", make_async_return(canned))
    monkeypatch.setattr(db, "is_available", make_async_return(True))

    r = await client.get("/v1/market/ohlcv/THYAO")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "THYAO"
    assert body["count"] == 2
    assert body["bars"][0]["close"] == 108.0


async def test_ohlcv_404_when_empty(client, monkeypatch):
    monkeypatch.setattr(db, "fetch", make_async_return([]))
    monkeypatch.setattr(db, "is_available", make_async_return(True))
    r = await client.get("/v1/market/ohlcv/MISSING")
    assert r.status_code == 404


async def test_quote_returns_change_pct(client, monkeypatch):
    ts = datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc)
    latest = _Row({"ticker": "THYAO", "close": 110.0, "volume": 500.0, "bar_start": ts})
    prev = _Row({"close": 100.0})
    monkeypatch.setattr(db, "fetchrow", make_async_iter([latest, prev]))
    monkeypatch.setattr(db, "is_available", make_async_return(True))

    r = await client.get("/v1/market/quote/THYAO")
    assert r.status_code == 200
    body = r.json()
    assert body["price"] == 110.0
    assert abs(body["change_pct"] - 10.0) < 0.0001


async def test_market_decisions_alias(client, monkeypatch):
    canned = _row([
        {"decision_id": "11111111-1111-1111-1111-111111111111",
         "portfolio_id": "22222222-2222-2222-2222-222222222222",
         "ticker": "THYAO", "action": "BUY", "confidence": 0.85,
         "position_size_pct": 0.05, "evidence_count": 3,
         "contradiction_score": 0.1, "compliance_status": "APPROVED",
         "effective_at": datetime(2024, 1, 2, tzinfo=timezone.utc),
         "created_at": datetime(2024, 1, 2, tzinfo=timezone.utc),
         "data_completeness": "FULL"},
    ])
    monkeypatch.setattr(db, "fetch", make_async_return(canned))
    monkeypatch.setattr(db, "is_available", make_async_return(True))

    r = await client.get("/v1/market/decisions")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["items"][0]["ticker"] == "THYAO"


async def test_indices_list(client):
    r = await client.get("/v1/market/indices")
    assert r.status_code == 200
    assert "XU100" in r.json()["indices"]