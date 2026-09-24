# 15 — Email System Overview

> Provider: SendGrid. Templates: Jinja2. Responsive HTML, dark-mode aware.

## Email Catalog

| Email             | Trigger                        | Recipients       | Word limit |
|-------------------|--------------------------------|------------------|------------|
| Morning Briefing  | Cron 08:30 TRT weekday         | All active users | 1,500      |
| Evening Summary   | Cron 19:00 TRT weekday         | All active users | 1,500      |
| Weekly Summary    | Cron 19:30 TRT Friday          | All active users | 4,000      |
| Monthly Report    | Cron 09:00 1st business day    | All active users | 10,000     |
| Critical Alert    | Event `alert.critical`         | Affected user    | 500        |
| Compliance Block  | Event `compliance.blocked`     | Compliance team  | 300        |
| Backtest Report   | Event `backtest.complete`      | Analysts + admins| 2,000      |

## Deliverability Targets

- Delivery rate: > 98%
- Inbox placement: > 95% (not spam)
- Time-to-inbox: < 30s for critical alerts
- Unsubscribe rate: < 0.5% (target)
