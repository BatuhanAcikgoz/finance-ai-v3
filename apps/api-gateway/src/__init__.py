"""Finance AI V3 API Gateway package."""

from __future__ import annotations

import logging
import sys

import structlog


def _configure_structlog() -> None:
    """Configure structlog so middleware + routes can emit structured logs.

    Import-safe: never raises. If structlog is already configured by a host
    process (e.g. uvicorn), we don't clobber it.
    """
    try:
        # Bridge stdlib logging into structlog so any 3rd-party log lines
        # (asyncpg, redis, uvicorn) are also structured.
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=logging.INFO,
        )

        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.dev.set_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    except Exception:  # pragma: no cover - never block import
        pass


_configure_structlog()

__all__ = ["__version__"]
__version__ = "0.1.0"