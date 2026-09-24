# 15/03 — SMTP Configuration

## SendGrid Setup

```yaml
# infra/docker/docker-compose.yml
notification-dispatch:
  environment:
    SMTP_HOST: smtp.sendgrid.net
    SMTP_PORT: 587
    SMTP_USER: apikey
    SMTP_PASSWORD: ${SENDGRID_API_KEY}
    SMTP_FROM: "Finance AI V3 <noreply@finance-ai-v3.local>"
    SMTP_REPLY_TO: "support@finance-ai-v3.local"
```

## DNS Records (required for deliverability)

```
# SPF
finance-ai-v3.local. IN TXT "v=spf1 include:sendgrid.net ~all"

# DKIM
s1._domainkey.finance-ai-v3.local. IN CNAME s1.domainkey.uXXX.wlXXX.sendgrid.net.
s2._domainkey.finance-ai-v3.local. IN CNAME s2.domainkey.uXXX.wlXXX.sendgrid.net.

# DMARC
_dmarc.finance-ai-v3.local. IN TXT "v=DMARC1; p=quarantine; rua=mailto:dmarc@finance-ai-v3.local"
```

## Rate Limits

- SendGrid: 100 emails/sec, 10,000/day (starter plan)
- Burst queue in Redis: if rate exceeded, queue and retry
- Per-user max: 10 emails/day (excluding critical alerts)

## Testing

- Test mode: all emails sent to `test+{user_id}@finance-ai-v3.local`
- Mailtrap for staging environment
- Manual trigger from `/settings` for any email type
