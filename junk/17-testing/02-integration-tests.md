# 17/02 — Integration Tests

## Conventions

- File: `tests/integration/test_{workflow}.py`
- Use `testcontainers` for real PostgreSQL, Redis, Qdrant
- Each test gets fresh containers (slow but isolated)

## Example

```python
# tests/integration/test_decision_pipeline.py
import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from testcontainers.qdrant import QdrantContainer

@pytest.fixture(scope="module")
def postgres():
    with PostgresContainer("postgres:16") as pg:
        yield pg

@pytest.fixture(scope="module")
def redis():
    with RedisContainer("redis:7") as r:
        yield r

@pytest.fixture(scope="module")
def qdrant():
    with QdrantContainer("qdrant/qdrant:v1.10.1") as q:
        yield q

@pytest.mark.asyncio
async def test_full_decision_pipeline(postgres, redis, qdrant):
    """End-to-end: ingest KAP → classify → fundamental analysis → decision."""
    # 1. Insert test KAP
    kap = await insert_kap(postgres, title="THYAO Q3 earnings", body="...")
    
    # 2. Trigger kap_collector workflow
    await trigger_workflow("kap_collector", {"since": "2026-07-28"})
    
    # 3. Wait for decision
    decision = await wait_for_decision(ticker="THYAO", timeout=120)
    
    # 4. Assertions
    assert decision.action in ("BUY", "HOLD", "INSUFFICIENT_EVIDENCE")
    assert decision.compliance_status == "APPROVED"
    assert len(decision.evidence) >= 3
    assert decision.data_completeness in ("complete", "partial")
```

## Test Data

- Fixtures in `tests/fixtures/`
- Anonymized real data (no PII)
- Sample KAP disclosures, news articles, price series
- Sample portfolios (small, medium, large)
