from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from middleware.logging import LoggingMiddleware
from middleware.rate_limit import RateLimitMiddleware
from routes import (
    admin,
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
    ws_market,  # WebSocket market feed (issue #1 / FR-005)
)
from services import decision_loop  # Phase-1 live decision loop (issue #7)

# Import-safe infra helpers — they no-op cleanly when DB/Redis are unreachable.
import db
import redis_cache

structlog = __import__('structlog')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Initializes the lazy asyncpg pool + Redis client at startup (best-effort —
    logs and continues if the infra is down) and tears them down on shutdown.
    The decision loop is started after the pool is ready so the first cycle
    has data to work with.
    """
    logger = structlog.get_logger()
    logger.info("api_gateway.starting", version="0.1.0")

    # Kick off background init so /health is responsive immediately, but
    # do not block startup — both helpers tolerate unreachable backends.
    pool = await db.get_pool()
    if pool is not None:
        await db.ensure_schema()
        # Seed the default admin/admin account if the users table is empty.
        await auth.ensure_default_admin()
    await redis_cache.get_client()  # lazy-connect; cheap

    # Start the Phase-1 live decision loop (issue #7). It self-suspends if
    # the pool is None and resumes on the next cycle once DB is back.
    loop = decision_loop.get_loop()
    loop.start()

    # Start the WebSocket tick engine (issue #1 / FR-005).
    tick_engine = ws_market.get_engine()
    tick_engine.start()

    try:
        yield
    finally:
        logger.info("api_gateway.shutdown")
        await tick_engine.stop()
        await loop.stop()
        await db.close_pool()
        await redis_cache.close_client()


app = FastAPI(
    title="Finance AI V3 API",
    description="Autonomous Financial Research Analyst for Turkish Capital Markets",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(LoggingMiddleware)

# CORS — origins are read from the FA_ALLOWED_ORIGINS env var (comma
# separated) so dev / preview / prod don't have to redeploy to add a host.
# Defaults include every address the docker stack and a local browser are
# realistically going to hit, so the most common case is "no config needed".
# CORS: NOT NEEDED now that nginx is removed and FastAPI serves both the
# dashboard static files AND the API on the same origin. Same-origin = no
# cross-origin = browser skips the CORS layer entirely. We keep an empty
# CORSMiddleware as a safety net for legacy cross-origin clients, but
# `allow_origins=[]` effectively disables it. If you ever need cross-origin
# support (e.g. mobile app), set FA_ALLOWED_ORIGINS to a comma-separated list.
import os as _os
_cors_env = _os.environ.get("FA_ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()]
if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Admin-Token-Required"],
        max_age=600,
    )
app.add_middleware(RateLimitMiddleware)

# Routes
app.include_router(health.router, prefix="/api/health", tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(market.router, prefix="/api/v1/market", tags=["Market"])
app.include_router(decisions.router, prefix="/api/v1/decisions", tags=["Decisions"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["Portfolio"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["Backtest"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(events.router, prefix="/api/v1/events", tags=["Events"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(ws_market.router, prefix="/api/v1/market", tags=["Market WS"])


# ─── Static dashboard (replaces the legacy nginx proxy) ─────────────────
# When nginx is removed, the FastAPI process becomes the single origin: the
# browser hits /admin.html and gets the HTML shell, /styles.css / side-nav.js
# / etc. load from this same origin, /api/v1/* routes are mounted right above.
# No CORS, no proxy_redirect, no duplicate ACAO header logic.
#
# Lookup order:
#   1. /api/* or /docs or /openapi.json → handled by the routers above.
#   2. /dashboard/<page>.html            → static file under dist/ (legacy).
#   3. /<page>.html                      → static file under dist/ directly.
#   4. / → serve dist/index.html.

_STATIC_DIR = Path(os.environ.get(
    "FA_STATIC_DIR",
    "/app/apps/dashboard/dist",   # inside the api-gateway image after COPY
))


def _resolve_static(path: str) -> Path | None:
    """Return the absolute file path for a static asset, or None if missing.

    The dashboard's index.html references scripts and stylesheets with
    relative paths like `./styles.css` or `./ui.js`, so when a browser
    visits /admin.html it may also request /styles.css. We resolve that
    directly against _STATIC_DIR.
    """
    if not _STATIC_DIR.exists():
        return None
    target = (_STATIC_DIR / path.lstrip("/")).resolve()
    try:
        target.relative_to(_STATIC_DIR.resolve())  # block path traversal
    except ValueError:
        return None
    return target if target.is_file() else None


@app.get("/", include_in_schema=False)
async def dashboard_root():
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/dashboard", include_in_schema=False)
async def dashboard_alias_root():
    return RedirectResponse(url="/index.html", status_code=302)


@app.get("/dashboard/{page:path}", include_in_schema=False)
async def dashboard_alias(page: str):
    """Back-compat alias — older deployments used /dashboard/ prefix."""
    target = _resolve_static(page)
    if target:
        return FileResponse(target)
    index_target = _resolve_static(page + ".html") if not page.endswith(".html") else None
    if index_target:
        return FileResponse(index_target)
    return RedirectResponse(url="/index.html", status_code=302)


if _STATIC_DIR.exists() and (_STATIC_DIR / "index.html").is_file():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=False), name="dashboard")
else:
    import logging
    logging.getLogger(__name__).warning(
        "dashboard static dir not found at %s — skipping mount", _STATIC_DIR
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
