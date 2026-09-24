# 14/03 — Real-Time WebSocket

## Connection

```typescript
// app/lib/ws.ts
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'wss://api.finance-ai-v3.local/ws';

export function connectWebSocket(token: string) {
  const ws = new WebSocket(`${WS_URL}?token=${token}`);
  
  ws.onopen = () => console.log('WS connected');
  ws.onclose = () => setTimeout(() => connectWebSocket(token), 5000); // reconnect
  ws.onerror = (e) => console.error('WS error', e);
  
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handleMessage(msg);
  };
  
  return ws;
}

function handleMessage(msg: WSMessage) {
  switch (msg.type) {
    case 'market.update':
      queryClient.setQueryData(['market', msg.ticker], msg.data);
      break;
    case 'decision.created':
      queryClient.invalidateQueries(['decisions']);
      toast.info(`New decision: ${msg.action} ${msg.ticker}`);
      break;
    case 'alert.new':
      if (msg.severity === 'CRITICAL' || msg.severity === 'EMERGENCY') {
        toast.error(msg.title_tr);
      }
      break;
  }
}
```

## Message Types

| Type                | Payload                                       |
|---------------------|-----------------------------------------------|
| `market.update`     | `{ticker, price, volume, ts}`                 |
| `decision.created`  | `{decision_id, ticker, action, confidence}`   |
| `alert.new`         | `{alert_id, severity, title_tr, body_tr}`     |
| `report.generated`  | `{report_id, report_type}`                    |
| `agent.activity`    | `{agent_name, status, last_call_at}`          |

## Backpressure

- If client can't keep up (queue > 100 messages), server drops `market.update` (lowest priority)
- Critical messages (`alert.new`, `decision.created`) never dropped
- Heartbeat every 30s; client must respond or be disconnected
