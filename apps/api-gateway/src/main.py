from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middleware.logging import LoggingMiddleware
from middleware.rate_limit import RateLimitMiddleware
from routes import (
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

# Import-safe infra helpers — they no-op cleanly when DB/Redis are unreachable.
import db
import redis_cache

structlog = __import__('structlog')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Initializes the lazy asyncpg pool + Redis client at startup (best-effort —
    logs and continues if the infra is down) and tears them down on shutdown.
    """
    logger = structlog.get_logger()
    logger.info("api_gateway.starting", version="0.1.0")

    # Kick off background init so /health is responsive immediately, but
    # do not block startup — both helpers tolerate unreachable backends.
    pool = await db.get_pool()
    if pool is not None:
        await db.ensure_schema()
    await redis_cache.get_client()  # lazy-connect; cheap

    try:
        yield
    finally:
        logger.info("api_gateway.shutdown")
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
