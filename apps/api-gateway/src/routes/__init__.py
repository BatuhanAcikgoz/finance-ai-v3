# Routes package — explicit re-exports make the surface easy to audit.
# Each new route module MUST be added here when wired into main.py.
from . import (  # noqa: F401
    agents,
    alerts,
    auth,
    backtest,
    decisions,
    events,
    health,
    market,
    portfolio,
    settings,
)

__all__ = [
    "agents",
    "alerts",
    "auth",
    "backtest",
    "decisions",
    "events",
    "health",
    "market",
    "portfolio",
    "settings",
]
