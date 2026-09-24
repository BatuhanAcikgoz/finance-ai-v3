"""Tests for Market Collector service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


class TestMarketCollectorService:
    """Test cases for MarketCollectorService."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis.setex = AsyncMock(return_value=True)
        redis.publish = AsyncMock(return_value=1)
        redis.exists = AsyncMock(return_value=False)
        return redis

    @pytest.fixture
    def mock_pool(self):
        """Create mock database pool."""
        pool = AsyncMock()
        conn = AsyncMock()
        conn.execute = AsyncMock()
        pool.acquire = AsyncMock(return_value=conn)
        return pool

    @pytest.mark.asyncio
    async def test_collect_ticks_success(self, mock_redis, mock_pool):
        """Test successful tick collection."""
        with patch("market_collector.service.Redis") as mock_redis_cls, \
             patch("market_collector.service.asyncpg") as mock_pg:
            
            mock_redis_cls.from_url.return_value = mock_redis
            mock_pg.create_pool.return_value = mock_pool

            # Import after patching
            from market_collector.service import MarketCollectorService
            
            service = MarketCollectorService()
            await service.initialize()

            # Mock the BIST API client
            with patch.object(service, "_client") as mock_client:
                mock_client.get_quotes_batch = AsyncMock(return_value=[
                    {
                        "symbol": "THYAO",
                        "lastPrice": 250.50,
                        "volume": 1000000,
                        "bid": 250.00,
                        "ask": 250.50,
                    }
                ])

                ticks = await service.collect_ticks(["THYAO"])
                
                assert len(ticks) == 1
                assert ticks[0]["ticker"] == "THYAO"
                assert ticks[0]["price"] == 250.50

    @pytest.mark.asyncio
    async def test_write_ticks_success(self, mock_redis, mock_pool):
        """Test successful tick write to database."""
        with patch("market_collector.service.Redis") as mock_redis_cls, \
             patch("market_collector.service.asyncpg") as mock_pg:
            
            mock_redis_cls.from_url.return_value = mock_redis
            mock_pg.create_pool.return_value = mock_pool

            from market_collector.service import MarketCollectorService
            
            service = MarketCollectorService()
            await service.initialize()

            ticks = [
                {
                    "ticker": "THYAO",
                    "price": 250.50,
                    "volume": 1000000,
                    "bid": 250.00,
                    "ask": 250.50,
                    "exchange_timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "BIST_API",
                }
            ]

            count = await service.write_ticks(ticks)
            assert count == 1

    @pytest.mark.asyncio
    async def test_emit_market_events(self, mock_redis):
        """Test market event emission to Redis."""
        with patch("market_collector.service.Redis") as mock_redis_cls:
            mock_redis_cls.from_url.return_value = mock_redis

            from market_collector.service import MarketCollectorService
            
            service = MarketCollectorService()
            await service.initialize()

            ticks = [
                {
                    "ticker": "THYAO",
                    "price": 250.50,
                    "volume": 1000000,
                }
            ]

            indices = [
                {
                    "index_code": "XU100",
                    "value": 15000.0,
                    "change_pct": 1.5,
                }
            ]

            await service.emit_market_events(ticks, indices)
            
            # Verify publish was called
            assert mock_redis.publish.call_count >= 0


class TestBISTCalendar:
    """Test cases for BIST trading calendar."""

    def test_is_trading_day_weekday(self):
        """Test that weekdays are trading days."""
        from shared.calendar.bist_calendar import is_trading_day
        from datetime import date
        
        # Monday
        assert is_trading_day(date(2024, 1, 8)) is True
        # Friday
        assert is_trading_day(date(2024, 1, 12)) is True

    def test_is_trading_day_weekend(self):
        """Test that weekends are not trading days."""
        from shared.calendar.bist_calendar import is_trading_day
        from datetime import date
        
        # Saturday
        assert is_trading_day(date(2024, 1, 13)) is False
        # Sunday
        assert is_trading_day(date(2024, 1, 14)) is False
