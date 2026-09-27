"""CORS regression — the dashboard admin panel broke because
ALLOWED_ORIGINS was hard-coded to localhost:3000/3001, missing the
8080/127.0.0.1 origin where this project actually runs.
"""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

import main as main_module


@pytest.mark.asyncio
async def test_default_cors_includes_dashboard_and_api_origins():
    """When FA_ALLOWED_ORIGINS isn't set, every realistic local origin
    must be on the list — otherwise the dashboard's XHR with X-Admin-Token
    will trip preflight CORS and fail silently in the browser console."""
    os.environ.pop("FA_ALLOWED_ORIGINS", None)
    # Reload module to pick up env change.
    import importlib
    importlib.reload(main_module)
    origins = main_module.ALLOWED_ORIGINS
    for required in [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        # Bare hostnames (no port = browser default). Without these, the
        # browser's Origin header gets no Access-Control-Allow-Origin back
        # and the dashboard fails with the classic 'CORS header missing'
        # console error.
        "http://localhost",
        "http://127.0.0.1",
    ]:
        assert required in origins, f"missing {required} in {origins}"


@pytest.mark.asyncio
async def test_origin_header_echoed_back():
    """An actual OPTIONS preflight from a known origin must come back
    with the matching Access-Control-Allow-Origin header."""
    async with AsyncClient(
        transport=ASGITransport(app=main_module.app),
        base_url="http://127.0.0.1:8080",
    ) as ac:
        r = await ac.options(
            "/v1/admin/llm/keys",
            headers={
                "Origin": "http://127.0.0.1:8080",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "x-admin-token,content-type",
            },
        )
    assert r.status_code == 200
    # Starlette returns Access-Control-Allow-Origin matching Origin (or *).
    acao = r.headers.get("access-control-allow-origin", "")
    assert acao in ("http://127.0.0.1:8080", "*"), f"ACAO={acao!r}"
    acam = r.headers.get("access-control-allow-methods", "")
    assert "POST" in acam.upper()


@pytest.mark.asyncio
async def test_custom_origin_via_env_var():
    """FA_ALLOWED_ORIGINS must let operators add dev/preview hosts
    without redeploying."""
    os.environ["FA_ALLOWED_ORIGINS"] = "https://preview.example,http://localhost:9999"
    try:
        import importlib
        importlib.reload(main_module)
        assert "https://preview.example" in main_module.ALLOWED_ORIGINS
        assert "http://localhost:9999" in main_module.ALLOWED_ORIGINS
        # previous defaults are gone (this is the whole point of the env).
        assert "http://localhost:3000" not in main_module.ALLOWED_ORIGINS
    finally:
        os.environ.pop("FA_ALLOWED_ORIGINS", None)
        importlib.reload(main_module)
