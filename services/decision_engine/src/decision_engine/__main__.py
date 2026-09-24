"""CLI entrypoint: python -m decision_engine

Aggregates technical + kap evidence into a recommendation, writes to postgres.
Loops every DECISION_ENGINE_INTERVAL_SECONDS (default 120).
"""
from __future__ import annotations

import asyncio
import os
import signal

import structlog

from decision_engine.service import DecisionEngineService

logger = structlog.get_logger("decision_engine.main")


async def _run_once() -> None:
    svc = DecisionEngineService()
    try:
        await svc.initialize()
        await svc.run()  # type: ignore[attr-defined]
        logger.info("decision_cycle_done")
    except AttributeError:
        logger.warning("decision_service_no_run_method")
    except Exception:  # noqa: BLE001
        logger.exception("decision_cycle_failed")
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

    interval = int(os.getenv("DECISION_ENGINE_INTERVAL_SECONDS", "120"))
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
