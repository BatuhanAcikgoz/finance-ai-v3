# 13/04 — Decision Traceability

## Every Decision Record Contains

```json
{
  "decision_id": "uuid",
  "evidence": [
    {
      "stream": "TECHNICAL",
      "signal": "BULLISH",
      "strength": 0.7,
      "confidence": 0.75,
      "source_id": "ta:THYAO:2026-07-28",
      "source_url": "https://...",
      "retrieved_at": "2026-07-28T10:30:00+03:00"
    },
    ...
  ],
  "weight_versions": {"TECHNICAL": "v1.2", "FUNDAMENTAL": "v1.2", ...},
  "prompt_versions": {"supervisor": "v1.0", "technical": "v1.0", ...},
  "computed_at": "2026-07-28T10:31:00+03:00",
  "computation_log": "weighted_signal=0.42, contradiction=0.08, ..."
}
```

## Trace Query

For any decision, the user can ask "why?":
```sql
SELECT * FROM decision.decisions WHERE decision_id = '...';
-- Returns full evidence[] array, prompt versions, weights, computation log
```

Each evidence item's `source_id` can be resolved to its origin:
- `ta:THYAO:2026-07-28` → row in `analysis.technical_indicators`
- `kap:12345` → row in `kap.disclosures`
- `news:abc-uuid` → row in `news.articles`
- `similar:hash` → Qdrant point

## Audit Trail

Every decision has:
1. The decision record itself
2. Compliance audit record (`audit.compliance_audits`)
3. Notification delivery log (`notification.deliveries`)
4. LLM call logs (with prompt + completion)
5. Workflow execution trace (OTel)

All retained for 2 years (7 years for compliance audit).
