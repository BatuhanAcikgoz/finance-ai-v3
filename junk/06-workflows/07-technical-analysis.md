# 06/07 — Technical Analysis

> **Owner agent:** Technical  ·  **Phase:** P1  ·  **SLA:** p50 < 500ms · p95 < 2s

---

## 1. Purpose

On every new bar (1m, 5m, 15m, 60m, daily), compute 40+ technical indicators and detect signal events (crossover, breakout, divergence).

## 2. Trigger

Event (`raw.market.bar.close`)

## 3. Input Schema

Reference: `09-json-schemas/01-market-data.md (Bar)`

## 4. Output Schema

Reference: `09-json-schemas/05-analysis-result.md (TechnicalAnalysis subtype)`

## 5. Steps

1. Receive bar close event with `{ticker, timeframe, close_time}`.
2. Fetch last 200 bars from PostgreSQL (or Redis cache).
3. Compute indicators using `pandas-ta`:
   - Trend: SMA(20,50,200), EMA(12,26), MACD, ADX, Parabolic SAR
   - Momentum: RSI(14), Stochastic, Williams %R, CCI
   - Volatility: Bollinger Bands, ATR, Keltner Channels
   - Volume: OBV, VWAP, MFI, CMF
   - Other: Ichimoku, Pivot Points
4. Detect signal events:
   - Golden cross (SMA50 crosses above SMA200)
   - Death cross (inverse)
   - RSI > 70 / RSI < 30
   - MACD crossover
   - Bollinger breakout
   - Volume spike (> 3σ vs. 20-day mean)
5. Insert indicators into PostgreSQL `technical_indicators` table.
6. For each detected signal → emit Redis event `analysis.technical.signal` for decision_engine.
7. Embed signal context into Qdrant for historical similarity search.

## 6. Error Handling

| Failure                          | Mitigation                                          |
|----------------------------------|-----------------------------------------------------|
| Insufficient bars (< 200)        | Compute partial indicator set; flag `partial: true` |
| NaN in indicator                 | Skip indicator; log; alert if frequent              |
| pandas-ta exception              | Catch; log stack; fallback to manual computation    |

## 7. n8n Nodes

- `Webhook` (trigger from market_collector)
- `Code` (pandas-ta computation)
- `Postgres` (insert indicators)
- `Redis` (publish signal events)
- `Qdrant` (embed signal context)

## 8. Test Cases

1. **Happy path:** 1 bar event → 40 indicators computed → 1 signal detected → event emitted.
2. **Edge:** New ticker with only 30 bars → SMA200 = NaN; `partial: true` flagged.
3. **Failure:** pandas-ta raises → caught, alert, fallback to manual SMA/RSI computation.

## 9. Idempotency

Key format: `technical:{ticker}:{timeframe}:{close_time_iso}`
- Stored in Redis with 24h TTL.
- Re-running with same key returns cached result.

## 10. SLA

- p50 latency: **< 500ms**
- p95 latency: **< 2s**
- Failure rate target: **< 1%**

## 11. Observability

- Every step emits OpenTelemetry span with `workflow_id`, `step_id`, `idempotency_key`.
- Workflow-level metrics: `workflow_duration_seconds`, `workflow_step_failures_total`, `workflow_retries_total`.
- All logs JSON-structured, `workflow_id` as correlation field.

## 12. Dependencies

- Upstream: see trigger
- Downstream: see output schema consumers
- External APIs: see step list
- LLM calls: via LiteLLM only (never direct SDK)
