"""CLI entrypoint: python -m technical_analysis

Reads OHLCV from postgres, computes indicators, writes them back.
Loops every TECHNICAL_ANALYSIS_INTERVAL_SECONDS (default 60).
"""
from __future__ import annotations

import asyncio
import os
import signal

import structlog

from technical_analysis.service import TechnicalAnalysisService

logger = structlog.get_logger("technical_analysis.main")


async def _run_once() -> None:
    svc = TechnicalAnalysisService()
    try:
        await svc.initialize()
        # Pull latest bars from postgres and process them.
        rows = await svc._fetch_bars(limit=50)  # type: ignore[attr-defined]
        if not rows:
            logger.info("technical_no_bars_yet")
            return
        count = 0
        for bar in rows:
            try:
                await svc.process_bar(bar)
                count += 1
            except Exception:  # noqa: BLE001
                logger.exception("technical_bar_failed", ticker=bar.get("ticker"))
        logger.info("technical_cycle_done", processed=count)
    except Exception:  # noqa: BLE001
        logger.exception("technical_cycle_failed")
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

    interval = int(os.getenv("TECHNICAL_ANALYSIS_INTERVAL_SECONDS", "60"))
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
