from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
_cors_env = os.environ.get(
    "FA_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:3001,"
    "http://localhost:8080,http://127.0.0.1:8080,"
    "http://localhost:8000,http://127.0.0.1:8000,"
    "http://localhost:5173,http://127.0.0.1:5173",
)
ALLOWED_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Admin-Token-Required"],
    max_age=600,  # cache preflight for 10 min
)
app.add_middleware(RateLimitMiddleware)

# Routes
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(auth.router, prefix="/v1/auth", tags=["Auth"])
app.include_router(market.router, prefix="/v1/market", tags=["Market"])
app.include_router(decisions.router, prefix="/v1/decisions", tags=["Decisions"])
app.include_router(alerts.router, prefix="/v1/alerts", tags=["Alerts"])
app.include_router(portfolio.router, prefix="/v1/portfolio", tags=["Portfolio"])
app.include_router(agents.router, prefix="/v1/agents", tags=["Agents"])
app.include_router(backtest.router, prefix="/v1/backtest", tags=["Backtest"])
app.include_router(settings.router, prefix="/v1/settings", tags=["Settings"])
app.include_router(events.router, prefix="/v1/events", tags=["Events"])
app.include_router(admin.router, prefix="/v1/admin", tags=["Admin"])
app.include_router(ws_market.router, prefix="/v1/market", tags=["Market WS"])


@app.get("/")
async def root():
    return {
        "name": "Finance AI V3 API",
        "version": "0.1.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
