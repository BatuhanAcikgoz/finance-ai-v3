# 16/03 — Distributed Tracing

## OpenTelemetry

Every service emits OTel traces. Sampling rate: 100% for errors, 10% for normal requests (to manage volume).

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def create_decision(payload):
    with tracer.start_as_current_span("create_decision") as span:
        span.set_attribute("ticker", payload["ticker"])
        span.set_attribute("portfolio_id", payload["portfolio_id"])
        
        # ... business logic
        
        span.set_attribute("decision_id", decision.id)
        span.set_attribute("action", decision.action)
        span.set_attribute("confidence", decision.confidence)
```

## Span Hierarchy

```
trace_id: abc123
└── span: workflow.execute (workflow_id=decision_engine, idempotency_key=...)
    ├── span: agent.dispatch (agent_name=technical, ticker=THYAO)
    │   └── span: litellm.complete (model=minimax-m3, tokens=1300)
    ├── span: agent.dispatch (agent_name=fundamental)
    │   └── span: litellm.complete (model=minimax-m3, tokens=2400)
    ├── span: agent.dispatch (agent_name=news)
    │   └── span: litellm.complete
    ├── span: aggregate_evidence
    ├── span: compute_confidence
    ├── span: portfolio.compute_context
    ├── span: compliance_check
    │   └── span: litellm.complete
    └── span: postgres.insert (table=decisions)
```

## Trace Querying (Jaeger)

Find slow decisions:
```
service=decision-engine operation=create_decision
duration > 5s
```

Find decisions where LLM failed:
```
service=litellm operation=complete
tags={"error": true}
```

Find decisions on specific ticker:
```
tags={"ticker": "THYAO"}
```
