# 17/04 — Load Tests (k6)

## Scenarios

| Scenario                | Tool | Target                            |
|-------------------------|------|-----------------------------------|
| API gateway peak        | k6   | 1000 RPS, p95 < 200ms             |
| Dashboard concurrent    | k6   | 50 users, p95 < 2s LCP            |
| WebSocket connections   | k6   | 200 concurrent, 0 msg loss        |
| Decision pipeline burst | k6   | 100 decisions in 10s              |
| LLM cost ceiling        | custom | Simulate 1000 decisions, < $500  |

## Example

```javascript
// tests/load/decision_pipeline.k6.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 50 },
    { duration: '30s', target: 100 },
    { duration: '1m', target: 100 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'],
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const payload = JSON.stringify({
    ticker: 'THYAO',
    portfolio_id: 'test-portfolio',
    trigger: 'manual_test',
  });
  
  const params = {
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${__ENV.TOKEN}` },
  };
  
  const res = http.post('https://api.finance-ai-v3.local/v1/decisions/trigger', payload, params);
  
  check(res, {
    'status 200 or 202': (r) => [200, 202].includes(r.status),
    'response time < 2s': (r) => r.timings.duration < 2000,
  });
  
  sleep(1);
}
```

## Run

```bash
k6 run tests/load/decision_pipeline.k6.js
```
