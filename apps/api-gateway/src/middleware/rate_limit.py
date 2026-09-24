
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# TODO: Implement with Redis
# from slowapi import Limiter
# from slowapi.util import get_remote_address


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis."""

    def __init__(self, app, redis_client=None, rate_limit: int = 100):
        super().__init__(app)
        self.redis_client = redis_client
        self.rate_limit = rate_limit
        self.window_seconds = 60

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path.startswith("/health"):
            return await call_next(request)

        # TODO: Implement Redis-based rate limiting
        # This is a placeholder that allows all requests through

        response = await call_next(request)
        return response
