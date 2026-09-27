from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
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


# Clean-URL routing + unified static handling.
# We deliberately do NOT use StaticFiles(..., mount="/") here because
# FastAPI mounts always match before routes — including the catch-all
# `/api/*` chains we register. Instead we route everything via the
# explicit handlers below. Path-only links (`/decisions`) and explicit
# links (`/decisions.html`) both land on the same file.
_CLEAN_URL_EXCLUDE = {"api", "docs", "redoc", "openapi.json", "favicon.ico"}


@app.get("/", include_in_schema=False)
async def dashboard_root():
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/dashboard", include_in_schema=False)
async def dashboard_alias_root():
    return RedirectResponse(url="/index.html", status_code=302)


@app.get("/", include_in_schema=False)
async def dashboard_root():
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/dashboard", include_in_schema=False)
async def dashboard_alias_root():
    return RedirectResponse(url="/index", status_code=302)


@app.get("/dashboard/{page:path}", include_in_schema=False)
async def dashboard_alias(page: str):
    """Back-compat alias — older deployments used /dashboard/ prefix."""
    return _serve_dashboard_path(page)


def _serve_dashboard_path(page: str):
    """Resolve `page` to a static file in dist/.

    Order of preference:
      1. exact `dist/<page>` (e.g. dist/decisions.html or dist/decisions)
      2. `dist/<page>.html` (clean URL fallback)
      3. nothing → redirect to /index
    """
    if not _STATIC_DIR.exists():
        raise HTTPException(status_code=404)
    first = page.split("/", 1)[0] if page else ""
    if first in _CLEAN_URL_EXCLUDE or first.startswith("api"):
        # Should have been caught by an earlier API route; this is a safety net.
        raise HTTPException(status_code=404)
    target = _resolve_static(page)
    if target:
        return FileResponse(target)
    if not page.endswith(".html"):
        target = _resolve_static(page + ".html")
        if target:
            return FileResponse(target)
    return RedirectResponse(url="/index", status_code=302)


# Catch-all: serves /<page> AND /<page>.html from dist/. Registered last so
# all the API routers above win their matches first. Path-only dashboard
# links (`/decisions`) work without a `/decisions.html` rewrite on the
# frontend; legacy `*.html` links still resolve.
# Catch-all handler REMOVED to avoid Starlette's 405 on path-only routes.
# Each dashboard page is registered explicitly below — see /index,
# /decisions, /portfolio, etc. Per-page routing also means `/api/*`
# won't be intercepted by this catch-all when the API routers happen
# to return 404 for an unknown path — the routers themselves will
# keep their 404/405 behaviour without our interference.


# Trailing-slash fallback for POST/PUT/PATCH/DELETE: the dashboard's
# admin form auto-appends `/` on POST (some browsers do this on form
# submit). FastAPI's `redirect_slashes` is GET-only; for unsafe methods
# we send a 308 Permanent Redirect so the body is preserved per RFC.
@app.api_route(
    "/api/v1/admin/llm/keys/",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
async def _llm_keys_trailing_slash_alias():
    return RedirectResponse(url="/api/v1/admin/llm/keys", status_code=308)


@app.api_route(
    "/api/v1/admin/llm/keys/{key_id}/test/",
    methods=["POST"],
    include_in_schema=False,
)
async def _llm_key_test_trailing_slash_alias(key_id: str):
    return RedirectResponse(
        url=f"/api/v1/admin/llm/keys/{key_id}/test", status_code=308
    )


# Per-page clean-URL routing. We can't use a generic catch-all because
# Starlette would treat unmatched methods on it as 405, breaking PATCH/
# POST for the API endpoints. So each dashboard page gets its own GET
# alias. Legacy `*.html` links still resolve via the explicit handlers
# above (`dashboard_alias`, etc.) and via the FastAPI static mount in
# the image's /app/apps/dashboard/dist directory, which the reverse-
# proxy layer in front of this used to expose as /<page>.html.
@app.get("/index", include_in_schema=False)
async def _page_index(): return _serve_dashboard_path("index.html")
@app.get("/decisions", include_in_schema=False)
async def _page_decisions(): return _serve_dashboard_path("decisions.html")
@app.get("/decision-detail", include_in_schema=False)
async def _page_decision_detail(): return _serve_dashboard_path("decision-detail.html")
@app.get("/portfolio", include_in_schema=False)
async def _page_portfolio(): return _serve_dashboard_path("portfolio.html")
@app.get("/alerts", include_in_schema=False)
async def _page_alerts(): return _serve_dashboard_path("alerts.html")
@app.get("/settings", include_in_schema=False)
async def _page_settings(): return _serve_dashboard_path("settings.html")
@app.get("/admin", include_in_schema=False)
async def _page_admin(): return _serve_dashboard_path("admin.html")
@app.get("/system-health", include_in_schema=False)
async def _page_system_health(): return _serve_dashboard_path("system-health.html")
@app.get("/login", include_in_schema=False)
async def _page_login(): return _serve_dashboard_path("login.html")


# Common asset route — supports /styles.css, /ui.js, /side-nav.js, etc.
# when the dashboard references them by bare filename rather than via the
# page route above.
@app.get("/styles.css", include_in_schema=False)
async def _styles_css(): return _serve_dashboard_path("styles.css")
@app.get("/styles.css.map", include_in_schema=False)
async def _styles_css_map(): return _serve_dashboard_path("styles.css.map")
@app.get("/favicon.svg", include_in_schema=False)
async def _favicon_svg(): return _serve_dashboard_path("favicon.svg")


# Backward-compatible .html aliases — older deployments used /<page>.html
# paths; we now serve /<page> (clean URLs) but accept both for users with
# stale bookmarks.
@app.get("/index.html", include_in_schema=False)
async def _p_index_html(): return _serve_dashboard_path("index.html")
@app.get("/decisions.html", include_in_schema=False)
async def _p_decisions_html(): return _serve_dashboard_path("decisions.html")
@app.get("/decision-detail.html", include_in_schema=False)
async def _p_decision_detail_html(): return _serve_dashboard_path("decision-detail.html")
@app.get("/portfolio.html", include_in_schema=False)
async def _p_portfolio_html(): return _serve_dashboard_path("portfolio.html")
@app.get("/alerts.html", include_in_schema=False)
async def _p_alerts_html(): return _serve_dashboard_path("alerts.html")
@app.get("/settings.html", include_in_schema=False)
async def _p_settings_html(): return _serve_dashboard_path("settings.html")
@app.get("/admin.html", include_in_schema=False)
async def _p_admin_html(): return _serve_dashboard_path("admin.html")
@app.get("/system-health.html", include_in_schema=False)
async def _p_system_health_html(): return _serve_dashboard_path("system-health.html")
@app.get("/login.html", include_in_schema=False)
async def _p_login_html(): return _serve_dashboard_path("login.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
