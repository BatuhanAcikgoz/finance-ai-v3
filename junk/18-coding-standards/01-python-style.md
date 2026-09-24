# 18/01 — Python Style

## ruff config

```toml
# pyproject.toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = [
  "E",   # pycodestyle errors
  "W",   # pycodestyle warnings
  "F",   # pyflakes
  "I",   # isort
  "B",   # bugbear
  "C4",  # comprehensions
  "UP",  # pyupgrade
  "N",   # pep8-naming
  "SIM", # simplify
  "ASYNC", # async lints
  "S",   # bandit-style security
  "T20", # no print()
  "RET", # return lints
  "PTH", # use pathlib
]
ignore = ["E501"]  # line length handled by formatter

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

## mypy config

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
```

## Patterns

### Use async for I/O
```python
# GOOD
async def fetch_ticker(ticker: str) -> Tick:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_URL}/tickers/{ticker}")
        return Tick(**response.json())

# BAD
def fetch_ticker(ticker: str) -> Tick:
    response = requests.get(f"{API_URL}/tickers/{ticker}")  # blocks event loop
    return Tick(**response.json())
```

### Type hints mandatory
```python
# GOOD
def compute_var(returns: np.ndarray, alpha: float = 0.95) -> float:
    ...

# BAD
def compute_var(returns, alpha=0.95):
    ...
```

### Use Pydantic for I/O boundaries
```python
from pydantic import BaseModel

class Tick(BaseModel):
    ticker: str
    price: float
    volume: float
    timestamp: datetime

# At API boundary, validate
tick = Tick(**incoming_dict)
```

### Use structlog, never print
```python
# GOOD
import structlog
log = structlog.get_logger()
log.info("decision_created", decision_id=d.id, ticker=d.ticker)

# BAD
print(f"Decision created: {d.id}")
```

### Use pathlib, never os.path
```python
# GOOD
from pathlib import Path
config_path = Path(__file__).parent / "config.yaml"

# BAD
import os
config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
```

### No global mutable state
```python
# BAD
_cache: dict = {}

def get_ticker(ticker: str):
    if ticker not in _cache:
        _cache[ticker] = fetch(ticker)
    return _cache[ticker]

# GOOD — use pydantic-settings + dependency injection
class TickerService:
    def __init__(self, cache: Redis):
        self.cache = cache
    
    async def get(self, ticker: str):
        cached = await self.cache.get(f"tick:{ticker}")
        if cached:
            return Tick.model_validate_json(cached)
        # ... fetch and cache
