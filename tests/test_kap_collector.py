"""Tests for KAP Collector service."""
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone


class TestKAPCollectorService:
    """Test cases for KAPCollectorService."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis.exists = AsyncMock(return_value=False)
        redis.publish = AsyncMock(return_value=1)
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
    async def test_classify_category_financial_report(self, mock_redis, mock_pool):
        """Test classification of financial report disclosure."""
        with patch("kap_collector.service.Redis") as mock_redis_cls, \
             patch("kap_collector.service.asyncpg") as mock_pg:
            
            mock_redis_cls.from_url.return_value = mock_redis
            mock_pg.create_pool.return_value = mock_pool

            from kap_collector.service import KAPCollectorService
            
            service = KAPCollectorService()
            
            disclosure = {
                "title": "2024 Q3 Financial Results",
                "content": "Quarterly earnings report",
            }
            
            category = service._classify_category(disclosure)
            assert category == "FINANCIAL_REPORT"

    @pytest.mark.asyncio
    async def test_classify_category_dividend(self, mock_redis, mock_pool):
        """Test classification of dividend disclosure."""
        with patch("kap_collector.service.Redis") as mock_redis_cls, \
             patch("kap_collector.service.asyncpg") as mock_pg:
            
            mock_redis_cls.from_url.return_value = mock_redis
            mock_pg.create_pool.return_value = mock_pool

            from kap_collector.service import KAPCollectorService
            
            service = KAPCollectorService()
            
            disclosure = {
                "title": "Temettü Dağıtımı",
                "content": "Dividend distribution announcement",
            }
            
            category = service._classify_category(disclosure)
            assert category == "DIVIDEND"

    @pytest.mark.asyncio
    async def test_detect_materiality_positive(self, mock_redis, mock_pool):
        """Test materiality detection for positive case."""
        with patch("kap_collector.service.Redis") as mock_redis_cls, \
             patch("kap_collector.service.asyncpg") as mock_pg:
            
            mock_redis_cls.from_url.return_value = mock_redis
            mock_pg.create_pool.return_value = mock_pool

            from kap_collector.service import KAPCollectorService
            
            service = KAPCollectorService()
            
            disclosure = {
                "title": "Önemli Karlar Açıklandı",
                "content": "Important profit announcement",
            }
            
            is_material = service._detect_materiality(disclosure)
            assert is_material is True

    @pytest.mark.asyncio
    async def test_extract_tickers(self, mock_redis, mock_pool):
        """Test ticker extraction from disclosure."""
        with patch("kap_collector.service.Redis") as mock_redis_cls, \
             patch("kap_collector.service.asyncpg") as mock_pg:
            
            mock_redis_cls.from_url.return_value = mock_redis
            mock_pg.create_pool.return_value = mock_pool

            from kap_collector.service import KAPCollectorService
            
            service = KAPCollectorService()
            
            disclosure = {
                "title": "THYAO and EREGL Merged",
                "content": "Turkish Airlines and Erdemir merger",
            }
            
            tickers = service._extract_tickers(disclosure)
            assert "THYAO" in tickers
            assert "EREGL" in tickers
