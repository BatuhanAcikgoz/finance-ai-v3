# 15/02 — Email Triggers

## Schedule-Triggered

| Email           | Cron                        | Timezone |
|-----------------|-----------------------------|----------|
| Morning Briefing| `30 8 * * 1-5`              | TRT      |
| Evening Summary | `0 19 * * 1-5`              | TRT      |
| Weekly Summary  | `30 19 * * 5`               | TRT      |
| Monthly Report  | `0 9 1-7 * 1` (1st Mon)     | TRT      |

## Event-Triggered

| Email             | Event                          | Condition                                |
|-------------------|--------------------------------|------------------------------------------|
| Critical Alert    | `alert.critical`               | Always (no rate limit on this)           |
| Compliance Block  | `compliance.blocked`           | Always                                   |
| Backtest Report   | `backtest.complete`            | Always                                   |
| Risk Budget Exceeded | `alert.risk.exceeded`       | Always                                   |

## Suppression Rules

- If user has unsubscribed from `weekly_summary`, skip
- If user has set "do not disturb" hours (e.g. 23:00-07:00), queue non-critical for next morning
- If user has no portfolio holdings, skip portfolio-specific emails
- If system in maintenance mode, skip all non-critical emails
