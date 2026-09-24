# 12/05 — Risk Alerting Rules

## Alert Catalog

| Rule                                    | Severity  | Channel                |
|-----------------------------------------|-----------|------------------------|
| VaR > 3% daily                          | WARN      | Email + dashboard      |
| VaR > 5% daily                          | CRITICAL  | Email + Slack + WS     |
| VaR > risk_budget_pct                   | CRITICAL  | Email + Slack + WS     |
| Single-holding weight > 25%             | WARN      | Email                  |
| Single-holding weight > 40%             | CRITICAL  | Email + Slack + WS     |
| Sector exposure > 40%                   | WARN      | Email                  |
| Sector exposure > 50%                   | CRITICAL  | Email + Slack + WS     |
| Beta > 1.5                              | WARN      | Email                  |
| Beta > 2.0                              | CRITICAL  | Email + Slack + WS     |
| HHI > 0.20 (high concentration)         | WARN      | Email                  |
| HHI > 0.35                              | CRITICAL  | Email + Slack + WS     |
| Tracking error > 10%                    | WARN      | Email                  |
| Drift from target > 5%                  | INFO      | Dashboard              |
| Drift from target > 10%                 | WARN      | Email                  |
| VaR breach (actual loss > VaR)          | CRITICAL  | Email + Slack + WS     |
| Kupiec test p-value < 0.05              | WARN      | Email to risk team     |

## Rate Limiting

- Max 5 CRITICAL alerts per portfolio per day
- Max 1 INFO per ticker per hour (drift)
- Dedup by `alert_id` within 60 min window
