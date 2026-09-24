# Test Stratejisi

Finance AI V3 için test stratejisi ve yazım rehberi.

## 📋 İçindekiler

1. [Test Türleri](#test-türleri)
2. [Test Yapısı](#test-yapısı)
3. [Unit Testler](#unit-testler)
4. [Integration Testler](#integration-testler)
5. [Test Fixtures](#test-fixtures)
6. [Mock Kullanımı](#mock-kullanımı)
7. [CI/CD Entegrasyonu](#cicd-entegrasyonu)

---

## Test Türleri

```
┌─────────────────────────────────────────────────────────────────┐
│                      TEST PİRAMİDİ                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│                         ▲                                        │
│                        /E\                                       │
│                       /2E\        E2E Tests                       │
│                      /────\       (10%)                          │
│                     /      \                                     │
│                    /  Int  \      Integration Tests              │
│                   /──────────\     (30%)                         │
│                  /            \                                  │
│                 /   Unit Tests \    Unit Tests                   │
│                /────────────────\   (60%)                        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

| Seviye | Miktar | Süre | Odak |
|--------|--------|------|------|
| Unit | 60% | < 1s | Fonksiyonlar |
| Integration | 30% | 1-10s | Servisler |
| E2E | 10% | 10s+ | Sistem |

---

## Test Yapısı

```
tests/
├── unit/
│   ├── test_decision_engine.py
│   ├── test_portfolio_engine.py
│   └── test_technical_indicators.py
├── integration/
│   ├── test_api_endpoints.py
│   └── test_database_operations.py
├── fixtures/
│   └── conftest.py
└── pytest.ini
```

### pytest.ini

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
```

---

## Unit Testler

### Örnek: Decision Engine

```python
# tests/unit/test_decision_engine.py
import pytest
from decision_engine.service import DecisionEngineService
from decision_engine.models import Evidence, EvidenceStream, Signal

class TestDecisionEngine:
    
    @pytest.fixture
    def service(self):
        return DecisionEngineService()
    
    @pytest.fixture
    def sample_evidence(self):
        return [
            Evidence(
                stream=EvidenceStream.TECHNICAL,
                signal=Signal.BULLISH,
                strength=0.8,
                confidence=0.75,
                source_id="tech_1"
            ),
            Evidence(
                stream=EvidenceStream.FUNDAMENTAL,
                signal=Signal.BULLISH,
                strength=0.7,
                confidence=0.70,
                source_id="fund_1"
            ),
        ]
    
    def test_aggregate_evidence(self, service, sample_evidence):
        """Test evidence aggregation returns weighted signal."""
        result = service._aggregate_evidence(sample_evidence)
        
        assert result.weighted_signal > 0
        assert result.evidence_count == 2
    
    def test_compute_confidence(self, service, sample_evidence):
        """Test confidence calculation."""
        aggregated = service._aggregate_evidence(sample_evidence)
        confidence = service._compute_confidence(aggregated)
        
        assert 0 <= confidence <= 1
    
    def test_determine_action_buy(self, service):
        """Test BUY action for strong bullish signal."""
        action = service._determine_action(
            confidence=0.75,
            weighted_signal=0.6,
            current_weight=0.05
        )
        
        assert action == Action.BUY
    
    def test_determine_action_hold_low_confidence(self, service):
        """Test HOLD action for low confidence."""
        action = service._determine_action(
            confidence=0.3,
            weighted_signal=0.6,
            current_weight=0.05
        )
        
        assert action == Action.INSUFFICIENT_EVIDENCE
```

### Örnek: Technical Indicators

```python
# tests/unit/test_technical_indicators.py
import pytest
import pandas as pd
import numpy as np
from technical_analysis.indicators import TechnicalIndicators

class TestTechnicalIndicators:
    
    @pytest.fixture
    def sample_data(self):
        """Generate sample OHLCV data."""
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        return pd.DataFrame({
            "close": 100 + np.cumsum(np.random.randn(100)),
            "high": 102 + np.cumsum(np.random.randn(100)),
            "low": 98 + np.cumsum(np.random.randn(100)),
            "volume": np.random.randint(1000000, 10000000, 100),
        })
    
    def test_rsi_calculation(self, sample_data):
        """Test RSI indicator calculation."""
        rsi = TechnicalIndicators.compute_rsi(sample_data["close"], period=14)
        
        assert len(rsi) == len(sample_data)
        assert all((rsi >= 0) & (rsi <= 100))
    
    def test_macd_calculation(self, sample_data):
        """Test MACD indicator calculation."""
        macd, signal, hist = TechnicalIndicators.compute_macd(
            sample_data["close"],
            fast=12,
            slow=26,
            signal=9
        )
        
        assert len(macd) == len(sample_data)
        assert len(signal) == len(sample_data)
        assert len(hist) == len(sample_data)
```

---

## Integration Testler

### Örnek: API Endpoints

```python
# tests/integration/test_api_endpoints.py
import pytest
from httpx import AsyncClient
from app.main import app

class TestPortfolioAPI:
    
    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer test_token"}
    
    @pytest.mark.asyncio
    async def test_create_portfolio(self, auth_headers):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/portfolios",
                json={
                    "name": "Test Portfolio",
                    "base_currency": "TRY"
                },
                headers=auth_headers
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "Test Portfolio"
            assert "portfolio_id" in data
    
    @pytest.mark.asyncio
    async def test_get_portfolios(self, auth_headers):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/portfolios",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            assert isinstance(response.json(), list)
```

### Örnek: Database Operations

```python
# tests/integration/test_database_operations.py
import pytest
from shared.db import get_db_pool

class TestDatabaseOperations:
    
    @pytest.fixture
    async def pool(self):
        p = get_db_pool()
        await p.init()
        yield p
        await p.close()
    
    @pytest.mark.asyncio
    async def test_insert_and_retrieve_ticker(self, pool):
        """Test ticker insertion and retrieval."""
        ticker = "TEST"
        name = "Test Company"
        
        async with pool.connection() as conn:
            # Insert
            await conn.execute(
                """
                INSERT INTO market_data.tickers (ticker, name)
                VALUES ($1, $2)
                ON CONFLICT (ticker) DO UPDATE SET name = $2
                """,
                ticker, name
            )
            
            # Retrieve
            row = await conn.fetchrow(
                "SELECT * FROM market_data.tickers WHERE ticker = $1",
                ticker
            )
            
            assert row is not None
            assert row["ticker"] == ticker
            assert row["name"] == name
```

---

## Test Fixtures

### conftest.py

```python
# tests/fixtures/conftest.py
import pytest
import asyncio
from typing import AsyncGenerator

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def db_pool():
    """Database pool fixture."""
    from shared.db import get_db_pool
    pool = get_db_pool()
    await pool.init()
    yield pool
    await pool.close()

@pytest.fixture
async def redis_client():
    """Redis client fixture."""
    from shared.redis import get_redis
    redis = get_redis()
    await redis.init()
    yield redis
    await redis.close()

@pytest.fixture
def sample_ticker_data():
    """Sample ticker data for tests."""
    return {
        "ticker": "THYAO",
        "name": "Türk Hava Yolları",
        "sector": "Havacılık",
    }

@pytest.fixture
def sample_portfolio_data():
    """Sample portfolio data for tests."""
    return {
        "name": "Test Portfolio",
        "base_currency": "TRY",
        "risk_budget_pct": 0.03,
        "max_position_pct": 0.25,
    }
```

---

## Mock Kullanımı

### API Mock

```python
# tests/unit/test_external_api.py
import pytest
from unittest.mock import AsyncMock, patch

class TestMarketCollector:
    
    @pytest.fixture
    def mock_bist_api(self):
        """Mock BIST API responses."""
        with patch("market_collector.client.BISTAPIClient") as mock:
            mock_instance = AsyncMock()
            mock_instance.get_quotes_batch.return_value = [
                {"symbol": "THYAO", "last": 180.50, "volume": 1500000}
            ]
            mock.return_value = mock_instance
            yield mock
    
    @pytest.mark.asyncio
    async def test_collect_ticks(self, mock_bist_api):
        """Test tick collection with mocked API."""
        from market_collector.service import MarketCollectorService
        
        service = MarketCollectorService("fake_api_key")
        await service.init()
        
        ticks = await service.collect_ticks(["THYAO"])
        
        assert len(ticks) == 1
        assert ticks[0]["ticker"] == "THYAO"
        assert ticks[0]["price"] == 180.50
```

### Redis Mock

```python
# tests/unit/test_redis_operations.py
import pytest
from unittest.mock import AsyncMock, MagicMock

class TestRedisOperations:
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis.publish = AsyncMock(return_value=1)
        return redis
    
    @pytest.mark.asyncio
    async def test_cache_set(self, mock_redis):
        """Test Redis cache set operation."""
        await mock_redis.set("key", "value")
        mock_redis.set.assert_called_once_with("key", "value")
```

---

## CI/CD Entegrasyonu

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install uv
        uses: astral-sh/setup-uv@v4
      
      - name: Install dependencies
        run: uv sync --all-packages
      
      - name: Run tests
        run: |
          pytest tests/ \
            --cov=src \
            --cov-report=xml \
            --cov-fail-under=80
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 24.1.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
```

---

## Test Coverage

### Hedefler

| Modül | Hedef Coverage |
|-------|----------------|
| Core Logic | 90%+ |
| API Handlers | 80%+ |
| Services | 85%+ |
| Overall | 80%+ |

### Coverage Raporu

```bash
# Coverage raporu oluştur
pytest tests/ --cov=src --cov-report=html --cov-report=term

# HTML raporu görüntüle
open htmlcov/index.html
```
