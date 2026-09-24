# 16/05 — Health Checks

## `/health` Endpoint

Every service exposes `GET /health` returning:

```json
{
  "status": "healthy | degraded | unhealthy",
  "service": "decision-engine",
  "version": "1.2.3",
  "uptime_seconds": 86400,
  "checks": {
    "postgres": {"status": "healthy", "latency_ms": 5},
    "redis": {"status": "healthy", "latency_ms": 2},
    "qdrant": {"status": "healthy", "latency_ms": 12},
    "litellm": {"status": "healthy", "latency_ms": 450},
    "disk": {"status": "healthy", "free_gb": 50.2},
    "memory": {"status": "healthy", "used_pct": 0.45}
  }
}
```

## Aggregated Health

`api-gateway` exposes `/v1/health/aggregate` that combines all services:

```json
{
  "status": "degraded",
  "services": {
    "market-collector": "healthy",
    "kap-collector": "healthy",
    "news-collector": "degraded",  // some RSS feeds down
    "supervisor": "healthy",
    "decision-engine": "healthy",
    ...
  }
}
```

## Kubernetes Probes

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

## Synthetic Monitoring

- External probe (e.g. UptimeRobot) hits `/v1/health/aggregate` every 30s
- Alert if `status != "healthy"` for > 1 min
- Monthly DR exercise: kill random containers, verify auto-recovery
