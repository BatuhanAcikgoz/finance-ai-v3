# 14/04 — Authentication & Authorization

## Auth Flow

1. User submits email + password to `/v1/auth/login`
2. Server verifies (bcrypt) + returns JWT (24h expiry)
3. Client stores JWT in httpOnly cookie
4. Every API request includes `Authorization: Bearer <jwt>`
5. WebSocket auth: JWT in query param on connect
6. Refresh: client calls `/v1/auth/refresh` 1h before expiry

## JWT Structure

```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "role": "viewer | analyst | admin",
  "iat": 1722169200,
  "exp": 1722255600
}
```

## Roles (RBAC)

| Role     | Permissions                                            |
|----------|--------------------------------------------------------|
| viewer   | Read-only: view portfolios, decisions, reports         |
| analyst  | viewer + edit portfolios, run backtests, approve weights |
| admin    | analyst + manage users, API keys, system settings      |

## API Key Authentication

For programmatic access:
- Generate API key in `/settings` (SHA-256 hashed at rest)
- Two scopes: `read-only`, `read-write`
- Rate limit: 100 req/min per key
- Logged in `audit.api_calls`

## Session Management

- Max 5 concurrent sessions per user
- Logout invalidates all sessions
- "Logout all devices" button in settings
