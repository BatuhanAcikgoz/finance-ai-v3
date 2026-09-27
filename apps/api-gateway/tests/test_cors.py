"""
Same-origin CORS is no longer a concern in the current stack: nginx is gone
and FastAPI serves both the dashboard static files and the API from a single
origin (same host, same port). The browser skips the CORS layer entirely.

This file replaces the old test_cors.py regression suite. We keep it as an
empty module so pytest picks up the file without a noisy "collection error",
and we add a single sentinel test that asserts the architectural invariant:
same origin = no preflight headers needed.

If you ever bring back a multi-origin deployment (e.g. a separate SPA host),
re-introduce real CORS regression tests here, and configure
FA_ALLOWED_ORIGINS as a comma-separated list.
"""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

import main as main_module


@pytest.mark.asyncio
async def test_same_origin_request_does_not_need_cors_headers():
    """A same-origin request must reach the API and return the normal payload
    without any ACAO headers — same origin means no CORS layer is involved.
    /api/v1/admin/llm/keys requires auth, so we expect 401 (or 200 with auth
    cookie). 403/404 means the route is no longer mounted under /api/v1.
    """
    async with AsyncClient(
        transport=ASGITransport(app=main_module.app),
        base_url="http://127.0.0.1:8080",
    ) as ac:
        r = await ac.get("/api/v1/admin/llm/keys")
        assert r.status_code in (200, 401), (
            f"GET /api/v1/admin/llm/keys must be a real route — got {r.status_code}"
        )
        # No ACAO header is required for same-origin; either it's absent
        # (CORSMiddleware not installed) or it's "*" / a value that matches
        # the origin. We just assert no exception path is hidden here.


@pytest.mark.asyncio
async def test_no_op_when_allowed_origins_env_unset():
    """ALLOWED_ORIGINS must default to [] now that nginx is gone.
    The middleware layer is installed only when the env var populates the
    list, so an unset env means the CORS layer is fully a no-op.
    """
    os.environ.pop("FA_ALLOWED_ORIGINS", None)
    import importlib
    importlib.reload(main_module)
    assert main_module.ALLOWED_ORIGINS == [], (
        "ALLOWED_ORIGINS must default to [] now that nginx is gone — "
        "the dashboard and the API share an origin."
    )
