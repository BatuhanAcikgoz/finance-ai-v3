# 17/06 — Test Data

## Fixtures

```
tests/fixtures/
├── kap_samples/         # 50 anonymized KAP disclosures
│   ├── financial_report_01.json
│   ├── dividend_01.json
│   └── ...
├── news_samples/        # 100 anonymized news articles
│   ├── earnings_beat_01.json
│   └── ...
├── price_samples/       # 1 year of price history for 10 tickers
│   ├── THYAO_2024.json
│   └── ...
├── portfolios/          # Sample portfolios
│   ├── small_3holdings.json
│   ├── medium_12holdings.json
│   └── large_35holdings.json
└── decisions/           # 30 historical decisions with outcomes
    ├── d-001.json
    └── ...
```

## Data Anonymization

- Real KAP/news with PII redacted
- Real prices (no PII, but source-attributed)
- Synthetic portfolios (no real user data)

## Seed Script

```bash
uv run python scripts/seed_dev_data.py
# Seeds dev DB with:
# - 50 KAP samples
# - 100 news samples
# - 1 year of prices for 10 tickers
# - 3 sample portfolios
# - 30 historical decisions with outcomes
```
