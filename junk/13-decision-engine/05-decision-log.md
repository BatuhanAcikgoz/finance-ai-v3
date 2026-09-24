# 13/05 — Decision Log Schema

## Table: `decision.decisions`

(see `10-database/01-postgres-schema.md` for full DDL)

## Querying the Decision Log

### "Show me all BUY decisions on THYAO last month"
```sql
SELECT decision_id, effective_at, confidence, position_size_pct, evidence_count
FROM decision.decisions
WHERE ticker = 'THYAO'
  AND action = 'BUY'
  AND effective_at >= NOW() - INTERVAL '1 month'
  AND compliance_status = 'APPROVED'
ORDER BY effective_at DESC;
```

### "Show me decisions where macro signal contradicted others"
```sql
SELECT *
FROM decision.decisions
WHERE evidence @> '[{"stream": "MACRO", "signal": "BEARISH"}]'::jsonb
  AND action = 'BUY'
  AND effective_at >= NOW() - INTERVAL '7 days';
```

### "What was the hit rate for HIGH-confidence decisions last quarter?"
```sql
SELECT 
    COUNT(*) FILTER (WHERE outcome_hit) AS hits,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE outcome_hit)::float / COUNT(*) AS hit_rate
FROM decision.decisions
WHERE confidence >= 0.7
  AND effective_at >= NOW() - INTERVAL '3 months'
  AND outcome_evaluated = TRUE;
```

## Retention

- Hot tier (PostgreSQL): 2 years
- Cold tier (S3 Parquet): 7 years (compliance requirement)
- Anonymization after 7 years (KVKK)
