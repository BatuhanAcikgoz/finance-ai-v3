"""Agent observability endpoints — cheap OTel-style approximation.

Real implementation: OpenTelemetry exporter → Tempo / Jaeger. For the
dashboard, we approximate by reading the last 100 lines of each agent's
docker container logs and parsing ``structlog`` JSON output.

Endpoints:
  GET /v1/agents                    → list of agents + status + 24h stats
  GET /v1/agents/{name}/calls       → paginated recent calls
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

import db

logger = logging.getLogger(__name__)
router = APIRouter()


def _err(error: str, detail: str) -> JSONResponse:
    """Standard 503 error response per gateway spec."""
    return JSONResponse(status_code=503, content={"error": error, "detail": detail})


# -- known agents -----------------------------------------------------------

KNOWN_AGENTS = (
    "technical_analysis",
    "decision_engine",
    "kap_collector",
    "report_generator",
)


# -- helpers ----------------------------------------------------------------

def _container_for(agent: str) -> str:
    """Map agent name → docker container name.

    Convention: ``finance-ai-v3-{agent}``. Override via env-style mapping in
    the future; for now we try a couple of fallbacks before giving up.
    """
    candidates = [
        f"finance-ai-v3-{agent}",
        f"finance_ai_v3_{agent}",
        agent,
    ]
    return candidates[0]


def _tail_container_logs(container: str, lines: int = 100) -> list[str]:
    """Return the last ``lines`` stdout/stderr lines of a docker container.

    Returns an empty list if docker is unreachable or the container doesn't
    exist — callers should treat empty as 'unknown' rather than an error.
    """
    try:
        proc = subprocess.run(
            ["docker", "logs", "--tail", str(lines), container],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if proc.returncode != 0:
            return []
        # stdout and stderr may both have content
        out = (proc.stdout or "") + (proc.stderr or "")
        return [ln for ln in out.splitlines() if ln.strip()]
    except Exception as exc:  # noqa: BLE001 — many ways docker can fail
        logger.debug("agents.docker_logs.unavailable container=%s err=%s",
                     container, str(exc))
        return []


# Match structlog JSONRenderer output: a line that *starts with* '{' and can
# be parsed as JSON. We accept partial lines too — if parse fails, we fall
# back to regex heuristics.
_STRUCTLOG_LINE_RE = re.compile(
    r'"event"\s*:\s*"(?P<event>[^"]+)"'
    r'.*?"timestamp"\s*:\s*"(?P<ts>[^"]+)"'
)


def _parse_log_lines(lines: list[str]) -> list[dict]:
    """Parse ``structlog`` JSON lines into normalized event dicts.

    Returns one dict per successfully-parsed line. Falls back to regex
    extraction when JSON parsing fails, then to ``{"raw": line}``.
    """
    out: list[dict] = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("{"):
            try:
                out.append(json.loads(ln))
                continue
            except json.JSONDecodeError:
                pass
        m = _STRUCTLOG_LINE_RE.search(ln)
        if m:
            out.append({
                "event": m.group("event"),
                "timestamp": m.group("ts"),
                "raw": ln,
            })
            continue
        out.append({"raw": ln})
    return out


def _agent_status(events: list[dict], now: datetime) -> tuple[str, Optional[str]]:
    """Heuristic: if we saw any event in the last 5 min, 'up'. Else 'down'.

    Returns ``(status, last_seen_iso)``. ``last_seen_iso`` may be None.
    """
    if not events:
        return "unknown", None
    # Collect timestamps
    last_seen: Optional[datetime] = None
    cutoff = now - timedelta(minutes=5)
    for ev in events:
        ts_str = ev.get("timestamp")
        if not ts_str:
            continue
        try:
            # structlog isoformat: "2024-01-02T03:04:05.678Z" or with offset
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if last_seen is None or ts > last_seen:
            last_seen = ts
    if last_seen is None:
        return "unknown", None
    return ("up" if last_seen >= cutoff else "down"), last_seen.isoformat()


def _summarize_window(events: list[dict], since: timedelta) -> dict:
    """Aggregate per-event metrics for events newer than ``since``."""
    cutoff = datetime.now(timezone.utc) - since
    calls = 0
    success = 0
    latencies: list[float] = []
    costs: list[float] = []
    for ev in events:
        ts_str = ev.get("timestamp")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts < cutoff:
                    continue
            except (ValueError, TypeError):
                pass
        calls += 1
        if ev.get("level") in (None, "info"):
            success += 1
        lat = ev.get("latency_ms")
        if isinstance(lat, (int, float)):
            latencies.append(float(lat))
        cost = ev.get("cost_usd")
        if isinstance(cost, (int, float)):
            costs.append(float(cost))

    avg_latency = (sum(latencies) / len(latencies)) if latencies else None
    total_cost = sum(costs)
    success_rate = (success / calls) if calls else None
    return {
        "calls": calls,
        "avg_latency_ms": avg_latency,
        "success_rate": success_rate,
        "total_cost_usd": total_cost,
    }


def _row_to_dict(row: Any) -> dict:
    return {
        "ts": row["ts"].isoformat() if row.get("ts") else None,
        "ticker": row.get("ticker"),
        "latency_ms": row.get("latency_ms"),
        "cost_usd": row.get("cost_usd"),
        "status": row.get("status"),
        "input_tokens": row.get("input_tokens"),
        "output_tokens": row.get("output_tokens"),
        "model": row.get("model"),
    }


# -- endpoints --------------------------------------------------------------

@router.get("/")
async def list_agents():
    """List known agents with status + 24h stats (from docker logs)."""
    try:
        now = datetime.now(timezone.utc)
        since = timedelta(hours=24)
        agents_out: list[dict] = []

        for name in KNOWN_AGENTS:
            container = _container_for(name)
            lines = _tail_container_logs(container, lines=100)
            events = _parse_log_lines(lines)
            status, last_seen = _agent_status(events, now)
            summary = _summarize_window(events, since)

            agents_out.append({
                "name": name,
                "status": status,
                "last_seen": last_seen,
                "calls_24h": summary["calls"],
                "avg_latency_ms_24h": summary["avg_latency_ms"],
                "success_rate_24h": summary["success_rate"],
                "total_cost_usd_24h": summary["total_cost_usd"],
            })

        return {"items": agents_out, "count": len(agents_out)}
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("agents.list.error: %s", str(exc))
        return _err("list_agents_failed", str(exc))


@router.get("/{name}/calls")
async def list_agent_calls(
    name: str,
    since: str = Query("24h", description="Window like '24h', '1h', '7d'"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
):
    """Recent calls for a single agent. Backed by docker log scraping.

    The ``since`` parameter accepts a compact duration like ``24h``, ``1h``,
    ``7d``, ``30m``. Falls back to 24h when the input is malformed.
    """
    try:
        # Parse `since` like "24h" / "1h" / "7d" / "30m"
        m = re.fullmatch(r"(\d+)([mhd])", since.strip())
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            delta = {
                "m": timedelta(minutes=n),
                "h": timedelta(hours=n),
                "d": timedelta(days=n),
            }[unit]
        else:
            delta = timedelta(hours=24)

        container = _container_for(name)
        lines = _tail_container_logs(container, lines=500)
        events = _parse_log_lines(lines)

        # Filter to window
        cutoff = datetime.now(timezone.utc) - delta
        filtered: list[dict] = []
        for ev in events:
            ts_str = ev.get("timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass
            filtered.append({
                "ts": ts_str,
                "ticker": ev.get("ticker"),
                "latency_ms": ev.get("latency_ms"),
                "cost_usd": ev.get("cost_usd"),
                "status": ev.get("level") or ev.get("status"),
                "input_tokens": ev.get("input_tokens"),
                "output_tokens": ev.get("output_tokens"),
                "model": ev.get("model"),
            })

        # Sort newest-first; we don't have guaranteed timestamps, so use
        # the parsed ts string as a stable key when present.
        filtered.sort(key=lambda e: e.get("ts") or "", reverse=True)
        page = filtered[offset: offset + limit]

        return {"items": page, "count": len(page), "total": len(filtered)}
    except Exception as exc:  # noqa: BLE001 — wrap per spec
        logger.exception("agents.calls.error: %s", str(exc))
        return _err("list_agent_calls_failed", str(exc))
