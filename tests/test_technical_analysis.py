"""Tests for Technical Analysis service."""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import AsyncMock, patch


class TestTechnicalIndicators:
    """Test cases for TechnicalIndicators computation."""

    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data for testing."""
        dates = pd.date_range("2024-01-01", periods=200, freq="D")
        closes = 100 + np.cumsum(np.random.randn(200) * 2)
        highs = closes + np.abs(np.random.randn(200))
        lows = closes - np.abs(np.random.randn(200))
        volumes = np.random.randint(1000000, 5000000, 200)
        
        return {
            "closes": pd.Series(closes, index=dates),
            "highs": pd.Series(highs, index=dates),
            "lows": pd.Series(lows, index=dates),
            "volumes": pd.Series(volumes, index=dates),
        }

    def test_compute_sma(self, sample_data):
        """Test SMA computation."""
        from technical_analysis.indicators import TechnicalIndicators
        
        result = TechnicalIndicators._compute_trend(sample_data["closes"])
        
        assert "sma_20" in result
        assert "sma_50" in result
        assert "sma_200" in result
        assert isinstance(result["sma_20"], float)

    def test_compute_rsi(self, sample_data):
        """Test RSI computation."""
        from technical_analysis.indicators import TechnicalIndicators
        
        result = TechnicalIndicators._compute_momentum(
            sample_data["closes"],
            sample_data["highs"],
            sample_data["lows"],
        )
        
        assert "rsi" in result
        assert 0 <= result["rsi"] <= 100

    def test_compute_bollinger_bands(self, sample_data):
        """Test Bollinger Bands computation."""
        from technical_analysis.indicators import TechnicalIndicators
        
        result = TechnicalIndicators._compute_volatility(
            sample_data["closes"],
            sample_data["highs"],
            sample_data["lows"],
        )
        
        assert "bb_upper" in result
        assert "bb_middle" in result
        assert "bb_lower" in result
        assert result["bb_upper"] > result["bb_middle"]
        assert result["bb_middle"] > result["bb_lower"]

    def test_compute_all_indicators(self, sample_data):
        """Test computing all indicators at once."""
        from technical_analysis.indicators import TechnicalIndicators
        
        result = TechnicalIndicators.compute_all(
            sample_data["closes"],
            sample_data["highs"],
            sample_data["lows"],
            sample_data["volumes"],
        )
        
        # Check that signals are present
        assert "signals" in result
        assert isinstance(result["signals"], list)


class TestTechnicalAnalysisService:
    """Test cases for TechnicalAnalysisService."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=False)
        redis.setex = AsyncMock(return_value=True)
        redis.publish = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def mock_pool(self):
        """Create mock database pool."""
        pool = AsyncMock()
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock()
        pool.acquire = AsyncMock(return_value=conn)
        return pool

    @pytest.mark.asyncio
    async def test_check_idempotency(self, mock_redis, mock_pool):
        """Test idempotency key generation."""
        with patch("technical_analysis.service.Redis") as mock_redis_cls, \
             patch("technical_analysis.service.asyncpg") as mock_pg:
            
            mock_redis_cls.from_url.return_value = mock_redis
            mock_pg.create_pool.return_value = mock_pool

            from technical_analysis.service import TechnicalAnalysisService
            
            service = TechnicalAnalysisService()
            
            key = service._check_idempotency("THYAO", "1d", "2024-01-01T00:00:00")
            assert key == "technical:THYAO:1d:2024-01-01T00:00:00"
