"""CLI entrypoint: python -m report_generator

Reads decisions from postgres, writes markdown reports to REPORTS_DIR.
Loops every REPORT_GENERATOR_INTERVAL_SECONDS (default 60).
"""
from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path

import structlog

from report_generator.service import ReportGeneratorService

logger = structlog.get_logger("report_generator.main")


async def _run_once() -> None:
    svc = ReportGeneratorService()
    try:
        await svc.initialize()
        await svc.run()  # type: ignore[attr-defined]
        logger.info("report_cycle_done")
    except AttributeError:
        logger.warning("report_service_no_run_method")
    except Exception:  # noqa: BLE001
        logger.exception("report_cycle_failed")
    finally:
        await svc.close()


async def _run_loop() -> None:
    stop = asyncio.Event()

    def _on_signal(*_: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            pass

    # Make sure /reports exists even if volume mount lags.
    Path(os.getenv("REPORTS_DIR", "/reports")).mkdir(parents=True, exist_ok=True)

    interval = int(os.getenv("REPORT_GENERATOR_INTERVAL_SECONDS", "60"))
    while not stop.is_set():
        await _run_once()
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


def main() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )
    asyncio.run(_run_loop())


if __name__ == "__main__":
    main()
