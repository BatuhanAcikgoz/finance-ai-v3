# 14/01 — Page Specifications

## Overview Page (`/`)

### Sections
1. **Header:** Logo, nav, user menu, last-updated time
2. **KPI Cards:** Total portfolio value (TRY), daily P&L, VaR (1d 95%), decision count today
3. **Today's Decisions:** Top 5 decisions (sorted by confidence × importance)
4. **Portfolio Snapshot:** Top 5 holdings with current weight vs target
5. **Alerts Inbox (preview):** Last 3 alerts with severity badges
6. **Market Snapshot:** BIST-100, USD/TRY, top gainers/losers
7. **System Status:** Mini pill (green = healthy)

### Data Sources
- `GET /v1/portfolio/{id}/state`
- `GET /v1/decisions?since=today&limit=5`
- `GET /v1/alerts?limit=3`
- `GET /v1/market/snapshot`
- WebSocket: `market.update`, `decision.created`, `alert.new`

## Decisions Page (`/decisions`)

### Filters
- Date range (default: last 7 days)
- Ticker
- Action (BUY/SELL/HOLD/REDUCE/INSUFFICIENT)
- Confidence range (slider)
- Compliance status

### Table Columns
| Decision ID (short) | Ticker | Action | Confidence | Position Size | Effective At | Compliance | Detail Link |
|---------------------|--------|--------|------------|---------------|--------------|------------|-------------|

### Decision Detail Page (`/decisions/[id]`)

Sections:
1. **Header:** Decision ID, ticker, action, confidence badge, effective at
2. **Action Summary:** Supervisor reasoning (Turkish), position size suggestion
3. **Evidence Trace (collapsible):** One card per evidence stream:
   - Stream name + signal direction
   - Strength + confidence bars
   - Source ID + link
   - Retrieved at
4. **Portfolio Context:** Current weight, post-trade weight, Kelly fraction
5. **Compliance Audit:** Status, reviewed at, violations (if any)
6. **LLM Call Logs:** Per-agent call (prompt version, tokens, latency, cost)
7. **Similar Past Decisions:** Top 5 from Qdrant (with outcome hit/miss)

## Agents Page (`/agents`)

### Layout
- Tabs: per agent (Supervisor, Technical, Fundamental, ...)
- Per agent:
  - Last 24h: call count, avg latency, success rate, total cost
  - Last 7d: time-series chart
  - Recent calls (table): timestamp, ticker, tokens, cost, status

## Backtest Page (`/backtest`)

### Sections
1. **Latest Report:** Hit-rate, calibration, weight adjustments proposed
2. **Historical Reports:** Table of past backtests
3. **Run New Backtest:** Form (date range, scope); submit; progress bar
4. **Weight Adjustment Approval:** If proposed, show diff; approve/reject buttons
