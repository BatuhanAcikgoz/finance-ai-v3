"""CLI entrypoint: python -m kap_collector

Run a one-shot poll then exit, or loop forever if KAP_LOOP=1.
Graceful: any unhandled error in poll_disclosures is logged, never raised.
"""
from __future__ import annotations

import asyncio
import os
import signal

import structlog

from kap_collector.service import KAPCollectorService

logger = structlog.get_logger("kap_collector.main")

LOOP_ENV = "KAP_LOOP"


async def _run_once() -> None:
    svc = KAPCollectorService()
    try:
        await svc.initialize()
        added, updated, skipped = await svc.poll_disclosures()
        logger.info(
            "kap_poll_done",
            added=added,
            updated=updated,
            skipped=skipped,
        )
    except Exception:  # noqa: BLE001 — top-level guard so the container stays up
        logger.exception("kap_poll_failed")
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

    while not stop.is_set():
        await _run_once()
        try:
            await asyncio.wait_for(stop.wait(), timeout=300)
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
    if os.getenv(LOOP_ENV, "1") == "1":
        asyncio.run(_run_loop())
    else:
        asyncio.run(_run_once())


if __name__ == "__main__":
    main()
