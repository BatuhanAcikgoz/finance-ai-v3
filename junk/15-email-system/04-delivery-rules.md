# 15/04 — Delivery Rules

## Retry Strategy

| Attempt | Delay    | Action on failure                  |
|---------|----------|------------------------------------|
| 1       | immediate| Log                                |
| 2       | 5 min    | Log + queue                        |
| 3       | 30 min   | Log + alert ops                    |
| 4       | 2 hours  | Log + alert ops + user dashboard   |
| 5       | 6 hours  | Give up; mark as failed            |

## Bounce Handling

- Hard bounce (invalid email): disable user's email notifications
- Soft bounce (inbox full, etc.): retry 3 times
- Spam complaint: immediately unsubscribe user

## Deduplication

- Hash: `{email_type}:{user_id}:{date}` for daily/weekly/monthly
- Hash: `{email_type}:{decision_id}` for critical alerts
- Redis key: `email:dedup:{hash}` with TTL = 24h for dailies, 7d for weeklies

## Tracking

- Open tracking: 1x1 pixel (privacy-friendly, no user agent)
- Click tracking: redirect through `email.finance-ai-v3.local/c/{hash}`
- Unsubscribe: link in every email footer
- Per-email stats: sent, delivered, opened, clicked, bounced
