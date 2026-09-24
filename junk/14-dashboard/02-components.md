# 14/02 — Component Library

## Core Components (shadcn/ui based)

| Component             | Purpose                                    |
|-----------------------|--------------------------------------------|
| `Button`              | Standard button                            |
| `Card`                | KPI card, evidence card                    |
| `Badge`               | Severity badge, action badge               |
| `Table`               | Decisions table, agents table              |
| `Dialog`              | Modal for confirmations                    |
| `Sheet`               | Slide-over for decision detail             |
| `Tabs`                | Agent activity tabs                        |
| `Slider`              | Confidence range filter                    |
| `DatePicker`          | Date range filter                          |
| `Toast`               | Real-time alerts                           |
| `Skeleton`            | Loading state                              |

## Custom Components

| Component                  | Purpose                                          |
|----------------------------|--------------------------------------------------|
| `ConfidenceMeter`          | Vertical bar showing confidence 0-1              |
| `EvidenceCard`             | One evidence item with stream, signal, source    |
| `DecisionTraceTree`        | Tree visualization of decision flow              |
| `PortfolioHeatmap`         | Holdings as heatmap (color = daily P&L)          |
| `SentimentGauge`           | Sentiment -1 to +1 gauge                         |
| `AgentActivityChart`       | Time-series of agent calls                       |
| `RiskDashboard`            | VaR, beta, HHI widgets                           |
| `TurkishNumberFormat`      | Format TRY with thousands separator             |
| `TimeAgo`                  | "5 dakika önce" relative time                    |

## Theming

- Light + dark mode (system preference)
- Colors:
  - Primary: `#2563EB` (blue-600)
  - Success/Bullish: `#16A34A` (green-600)
  - Danger/Bearish: `#DC2626` (red-600)
  - Warning: `#F59E0B` (amber-500)
  - Background: `#FFFFFF` (light) / `#0F172A` (dark)
- Typography: Inter (sans), JetBrains Mono (mono)
