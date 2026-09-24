"""Backtest endpoint tests — uses monkeypatched db helpers."""

from datetime import datetime, timezone
from decimal import Decimal

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


RUN_UUID = "11111111-1111-1111-1111-111111111111"
NOW = datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc)


async def test_list_backtests_returns_runs(client, monkeypatch):
    canned = _row([
        {
            "run_id": RUN_UUID,
            "started_at": NOW,
            "ended_at": NOW,
            "hit_rate": Decimal("0.620"),
            "total_trades": 100,
            "winning_trades": 62,
            "losing_trades": 38,
            "avg_return": Decimal("0.0180"),
            "sharpe": Decimal("1.4500"),
            "max_drawdown": Decimal("-0.1200"),
            "approved": False,
        },
    ])
    monkeypatch.setattr(db, "fetch", make_async_return(canned))
    monkeypatch.setattr(db, "is_available", make_async_return(True))

    r = await client.get("/v1/backtest/")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    item = body["items"][0]
    assert item["run_id"] == RUN_UUID
    assert item["hit_rate"] == 0.62
    assert item["total_trades"] == 100
    assert item["sharpe"] == 1.45
    assert item["approved"] is False


async def test_run_backtest_inserts_queued_row(client, monkeypatch):
    """POST /run should insert a row with ended_at NULL and return its UUID."""
    captured: dict = {}

    async def fake_execute(query, *args):
        captured["query"] = query
        captured["args"] = args
        return "INSERT 0 1"

    monkeypatch.setattr(db, "execute", fake_execute)
    monkeypatch.setattr(db, "is_available", make_async_return(True))

    r = await client.post("/v1/backtest/run", json={"scope": {"universe": "BIST30"}})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "queued"
    # Run UUID is generated server-side and is a valid UUID.
    import uuid as _uuid
    _uuid.UUID(body["run_id"])
    # The INSERT should pass the run_id, started_at, and a jsonb scope.
    assert "INSERT INTO analysis.backtest_runs" in captured["query"]
    args = captured["args"]
    assert isinstance(args[0], _uuid.UUID)
    assert args[2] == '{"universe": "BIST30"}'


async def test_approve_backtest_marks_approved(client, monkeypatch):
    """POST /{run_id}/approve should UPDATE approved=TRUE and approved_at=now()."""
    captured: dict = {}

    async def fake_execute(query, *args):
        captured["query"] = query
        captured["args"] = args
        return "UPDATE 1"

    monkeypatch.setattr(db, "execute", fake_execute)
    monkeypatch.setattr(db, "is_available", make_async_return(True))

    r = await client.post(f"/v1/backtest/{RUN_UUID}/approve")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "approved"
    assert body["run_id"] == RUN_UUID
    assert "approved_at" in body
    # UPDATE should target approved + approved_at.
    assert "UPDATE analysis.backtest_runs" in captured["query"]
    assert "approved = TRUE" in captured["query"]
