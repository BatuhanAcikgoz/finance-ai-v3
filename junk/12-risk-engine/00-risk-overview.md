# 12 — Risk Engine Overview

> Deterministic Python (numpy + pandas). No LLM. Output: `06-risk-assessment.md` schema.

## Risk Metrics Catalog

| Metric                  | Computation                         | Frequency       |
|-------------------------|-------------------------------------|-----------------|
| 1-day 95% VaR          | Historical simulation               | Daily + on event |
| 1-day 95% CVaR         | Tail mean of historical sim         | Daily + on event |
| Beta to BIST-100       | 1Y regression                       | Daily           |
| Tracking error         | 1Y std of (portfolio - bench) returns | Daily         |
| HHI concentration      | Σ(weight_i)²                        | On holding change |
| Sector exposure        | Σ holdings in sector                | On holding change |
| Style exposure         | Regression on style factors         | Weekly          |
| Factor exposures       | Multi-factor regression             | Weekly          |
| Liquidity score        | Avg days-to-trade                   | On holding change |
| Drawdown               | Max drawdown from peak              | Daily           |
| Sharpe ratio           | Mean(rf-spread) / std               | Monthly         |
| Sortino ratio          | Mean(rf-spread) / downside std      | Monthly         |
