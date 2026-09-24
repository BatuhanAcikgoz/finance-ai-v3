"""Market collector service - main business logic."""

import asyncio
from datetime import timedelta
from typing import Any

import structlog
from services.shared.src.shared.calendar import is_market_open
from services.shared.src.shared.db import get_db_pool
from services.shared.src.shared.redis import get_redis

from .client import BISTAPIClient, BISTWebSocketClient

logger = structlog.get_logger()


class MarketCollectorService:
    """
    Service for collecting BIST market data.
    
    Responsibilities:
    - Fetch tick data every 10 seconds during trading hours
    - Aggregate bars at multiple timeframes
    - Fetch index values
    - Write to PostgreSQL and Redis
    - Emit events to Redis for downstream consumers
    """

    def __init__(self, api_key: str):
        self.api_client = BISTAPIClient(api_key)
        self.ws_client = BISTWebSocketClient()
        self.db_pool = get_db_pool()
        self.redis = get_redis()

    async def init(self) -> None:
        """Initialize connections."""
        await self.api_client.init()
        await self.redis.init()
        logger.info("market_collector_initialized")

    async def close(self) -> None:
        """Close connections."""
        await self.api_client.close()
        await self.redis.close()
        logger.info("market_collector_closed")

    async def collect_ticks(self, tickers: list[str]) -> list[dict[str, Any]]:
        """
        Collect tick data for given tickers.
        
        Returns list of tick records.
        """
        quotes = await self.api_client.get_quotes_batch(tickers)
        
        ticks = []
        for quote in quotes:
            if not quote:
                continue
            
            tick = {
                "ticker": quote.get("symbol"),
                "price": float(quote.get("last", 0)),
                "volume": float(quote.get("volume", 0)),
                "bid": float(quote.get("bid", 0)),
                "ask": float(quote.get("ask", 0)),
                "exchange_timestamp": quote.get("timestamp"),
                "source": "BIST_API",
            }
            ticks.append(tick)
            
            # Cache in Redis
            await self.redis.set_json(
                f"tick:{tick['ticker']}:latest",
                tick,
                ttl=timedelta(seconds=30),
            )
        
        return ticks

    async def write_ticks(self, ticks: list[dict[str, Any]]) -> int:
        """Write ticks to PostgreSQL."""
        if not ticks:
            return 0
        
        pool = self.db_pool
        
        query = """
            INSERT INTO market_data.ticks (ticker, price, volume, bid, ask, exchange_timestamp, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        
        count = 0
        async with pool.connection() as conn:
            for tick in ticks:
                await conn.execute(
                    query,
                    tick["ticker"],
                    tick["price"],
                    tick["volume"],
                    tick.get("bid"),
                    tick.get("ask"),
                    tick["exchange_timestamp"],
                    tick["source"],
                )
                count += 1
        
        return count

    async def collect_index_values(self) -> list[dict[str, Any]]:
        """Collect BIST-100 and sector index values."""
        indices = []
        
        # Get BIST-100
        try:
            xu100 = await self.api_client.get_index_value("XU100")
            indices.append({
                "index_code": "XU100",
                "value": float(xu100.get("value", 0)),
                "change_pct": float(xu100.get("change", 0)),
                "as_of": xu100.get("timestamp"),
            })
        except Exception as e:
            logger.error("failed_to_fetch_xu100", error=str(e))
        
        # Get sector indices
        try:
            sectors = await self.api_client.get_sector_indices()
            for sector in sectors:
                indices.append({
                    "index_code": sector.get("code"),
                    "value": float(sector.get("value", 0)),
                    "change_pct": float(sector.get("change", 0)),
                    "as_of": sector.get("timestamp"),
                })
        except Exception as e:
            logger.error("failed_to_fetch_sector_indices", error=str(e))
        
        return indices

    async def write_index_values(self, indices: list[dict[str, Any]]) -> int:
        """Write index values to PostgreSQL."""
        if not indices:
            return 0
        
        pool = self.db_pool
        
        query = """
            INSERT INTO market_data.index_values (index_code, value, change_pct, as_of)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (index_code, as_of) DO NOTHING
        """
        
        count = 0
        async with pool.connection() as conn:
            for idx in indices:
                await conn.execute(
                    query,
                    idx["index_code"],
                    idx["value"],
                    idx.get("change_pct"),
                    idx["as_of"],
                )
                count += 1
        
        return count

    async def emit_market_events(self, ticks: list[dict[str, Any]], indices: list[dict[str, Any]]) -> None:
        """Emit market events to Redis for downstream consumers."""
        for tick in ticks:
            await self.redis.publish(
                "raw.market.tick",
                tick,
            )
        
        for idx in indices:
            await self.redis.publish(
                "raw.market.index",
                idx,
            )

    async def run_collection_cycle(self, tickers: list[str]) -> None:
        """Run one collection cycle."""
        try:
            # Collect ticks
            ticks = await self.collect_ticks(tickers)
            if ticks:
                await self.write_ticks(ticks)
                logger.debug("ticks_collected", count=len(ticks))
            
            # Collect indices
            indices = await self.collect_index_values()
            if indices:
                await self.write_index_values(indices)
                logger.debug("indices_collected", count=len(indices))
            
            # Emit events
            if ticks or indices:
                await self.emit_market_events(ticks, indices)
                
        except Exception as e:
            logger.error("collection_cycle_failed", error=str(e))

    async def run_continuous(self, tickers: list[str], interval_seconds: int = 10) -> None:
        """Run continuous collection during market hours."""
        logger.info("market_collector_started", tickers=tickers, interval=interval_seconds)
        
        while True:
            if is_market_open():
                await self.run_collection_cycle(tickers)
            else:
                logger.debug("market_closed_skipping")
            
            await asyncio.sleep(interval_seconds)


async def create_service() -> MarketCollectorService:
    """Factory function to create the service.
    
    Raises:
        ValueError: If BIST_API_KEY environment variable is not set.
    """
    import os
    api_key = os.getenv("BIST_API_KEY")
    if not api_key:
        raise ValueError(
            "BIST_API_KEY environment variable must be set. "
            "Obtain your API key from BIST and set it via: export BIST_API_KEY=<your-key>"
        )
    if api_key == "CHANGE_ME":
        raise ValueError(
            "BIST_API_KEY is set to placeholder 'CHANGE_ME'. "
            "Please set it to a valid API key from BIST."
        )
    service = MarketCollectorService(api_key)
    await service.init()
    return service
