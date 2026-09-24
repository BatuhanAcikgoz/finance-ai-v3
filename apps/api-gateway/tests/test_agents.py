"""Agents endpoint tests — uses monkeypatched docker log scraping."""

import json
import subprocess
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

import main as main_module
import routes.agents as agents_module


@pytest.fixture
async def client():
    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _make_structlog_line(event: str, ts: datetime, **extra) -> str:
    payload = {"event": event, "timestamp": ts.isoformat(), "level": "info"}
    payload.update(extra)
    return json.dumps(payload)


async def test_list_agents_returns_known_agents(client, monkeypatch):
    """Each known agent should appear in the response; docker-down agents
    should report status='unknown' rather than raising."""
    def fake_tail(container, lines=100):
        if "technical_analysis" in container:
            now = datetime.now(timezone.utc)
            lines = [
                _make_structlog_line("agent.call", now,
                                     ticker="THYAO", latency_ms=120,
                                     cost_usd=0.002, level="info"),
                _make_structlog_line("agent.call", now,
                                     ticker="GARAN", latency_ms=80,
                                     cost_usd=0.001, level="info"),
            ]
            return lines
        return []  # other containers have no logs / docker not running

    monkeypatch.setattr(agents_module, "_tail_container_logs", fake_tail)
    r = await client.get("/v1/agents/")
    assert r.status_code == 200
    body = r.json()
    names = {a["name"] for a in body["items"]}
    assert {"technical_analysis", "decision_engine", "kap_collector",
            "report_generator"} <= names
    # technical_analysis saw 2 calls → calls_24h=2, others 0.
    ta = next(a for a in body["items"] if a["name"] == "technical_analysis")
    assert ta["calls_24h"] == 2
    assert ta["status"] == "up"


async def test_list_agent_calls_parses_structlog(client, monkeypatch):
    """Calls endpoint should parse JSON structlog lines into normalized dicts."""
    now = datetime.now(timezone.utc)
    canned_lines = [
        _make_structlog_line("agent.call", now,
                             ticker="AKBNK", latency_ms=250,
                             cost_usd=0.005, level="info",
                             input_tokens=1200, output_tokens=300, model="gpt-4o"),
        _make_structlog_line("agent.call", now,
                             ticker="THYAO", latency_ms=180,
                             cost_usd=0.003, level="error",
                             input_tokens=900, output_tokens=200, model="gpt-4o"),
    ]
    monkeypatch.setattr(agents_module, "_tail_container_logs",
                        lambda container, lines=500: canned_lines)

    r = await client.get("/v1/agents/technical_analysis/calls?since=24h")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    tickers = {c["ticker"] for c in body["items"]}
    assert tickers == {"AKBNK", "THYAO"}
    # status field mirrors structlog level
    levels = {c["status"] for c in body["items"]}
    assert "info" in levels and "error" in levels
