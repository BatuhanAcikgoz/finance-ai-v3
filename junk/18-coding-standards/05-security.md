# 18/05 — Security

## Secrets Management

- **Production:** HashiCorp Vault
- **Staging:** Vault (dev mode)
- **Dev:** `.env` (gitignored), `.env.example` documents required vars
- **CI/CD:** GitHub Actions secrets

### Secret Rotation

| Secret type           | Rotation frequency |
|-----------------------|--------------------|
| API keys (BIST, KAP)  | 90 days            |
| LLM provider keys     | 90 days            |
| Database passwords    | 60 days            |
| JWT signing key       | 30 days            |
| TLS certificates      | 90 days (auto via cert-manager) |

## Encryption

- **At rest:** AES-256 (PostgreSQL TDE, Qdrant disk encryption, EBS encryption)
- **In transit:** TLS 1.3 everywhere (no TLS 1.0/1.1/1.2)
- **mTLS** between internal services (self-signed CA in Docker, cert-manager in k8s)

## Input Validation

- All HTTP inputs validated by Pydantic models
- All LLM JSON outputs validated by JSON Schema
- All database queries use parameterized bindings (no f-strings in SQL)
- File uploads: MIME type check + size limit + virus scan (ClamAV)

## Authentication

- bcrypt for password hashing (cost factor 12)
- JWT for sessions (24h expiry, refresh 1h before)
- API keys: SHA-256 hashed at rest, displayed once on creation
- 2FA optional (TOTP via authenticator app)

## Authorization

- RBAC: viewer, analyst, admin
- Every endpoint decorated with required role
- Every WebSocket channel checks user authorization

## Audit Log

```sql
CREATE TABLE audit.api_calls (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,
    api_key_id UUID,
    endpoint VARCHAR(200),
    method VARCHAR(10),
    status_code INTEGER,
    request_body_hash CHAR(64),
    response_size_bytes INTEGER,
    ip_address INET,
    user_agent TEXT,
    called_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE audit.dashboard_logins (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN,
    logged_in_at TIMESTAMPTZ
);
```

## SAST/DAST

- **SAST:** bandit (Python), eslint security plugin (TS)
- **DAST:** OWASP ZAP weekly scan against staging
- **Dependency scan:** pip-audit (Python), npm audit (JS/TS)
- **Secret scan:** trufflehog on every commit + pre-commit hook

## Incident Response

1. **Detect:** alert from monitoring OR user report
2. **Triage:** on-call assesses severity
3. **Contain:** revoke compromised keys, block IP
4. **Eradicate:** fix vulnerability, deploy patch
5. **Recover:** restore service, verify
6. **Postmortem:** blameless review within 7 days
