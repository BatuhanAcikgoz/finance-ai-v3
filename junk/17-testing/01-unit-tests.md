# 17/01 — Unit Tests

## Conventions

- File: `tests/unit/{service}/test_{module}.py`
- Function: `test_{behavior}_{condition}`
- One assert per test (ideally; max 3)
- AAA pattern: Arrange, Act, Assert

## Example

```python
# tests/unit/decision_engine/test_confidence_scoring.py
import pytest
from decision_engine.confidence import compute_confidence

class TestComputeConfidence:
    def test_high_signal_low_contradiction_returns_high_confidence(self):
        # Arrange
        weighted_signal = 0.8
        contradiction_score = 0.05
        evidence_count = 5
        source_reliability = 0.9
        data_freshness = 1.0
        
        # Act
        result = compute_confidence(
            weighted_signal, contradiction_score, evidence_count,
            source_reliability, data_freshness
        )
        
        # Assert
        assert 0.6 < result < 0.8
    
    def test_zero_signal_returns_zero_confidence(self):
        result = compute_confidence(0, 0, 5, 1.0, 1.0)
        assert result == 0
    
    def test_high_contradiction_reduces_confidence(self):
        low_contradiction = compute_confidence(0.8, 0.1, 5, 1.0, 1.0)
        high_contradiction = compute_confidence(0.8, 0.6, 5, 1.0, 1.0)
        assert high_contradiction < low_contradiction * 0.7
    
    def test_low_evidence_count_reduces_confidence(self):
        full_evidence = compute_confidence(0.8, 0.1, 5, 1.0, 1.0)
        low_evidence = compute_confidence(0.8, 0.1, 2, 1.0, 1.0)
        assert low_evidence < full_evidence
    
    def test_confidence_capped_at_one(self):
        result = compute_confidence(1.0, 0, 10, 1.0, 1.0)
        assert result == 1.0
```

## Coverage

- Run: `uv run pytest --cov=services --cov-report=html --cov-fail-under=80`
- Per-service threshold: 80% lines, 70% branches
- Exclude from coverage: `__init__.py`, `main.py`, migration scripts
