# 10/06 — Data Retention Policy

> Compliance with KVKK (Turkish GDPR) + operational efficiency.

## Retention by Data Type

| Data                           | Store       | Retention  | Action after       |
|--------------------------------|-------------|------------|--------------------|
| Tick data                      | PostgreSQL  | 13 months  | Drop old partition |
| Bar data                       | PostgreSQL  | 5 years    | Drop old partition |
| KAP disclosures                | PostgreSQL  | Indefinite | N/A (regulatory)  |
| News articles                  | PostgreSQL  | 2 years    | Anonymize body     |
| Decisions                      | PostgreSQL  | 2 years    | Move to cold storage|
| Compliance audits              | PostgreSQL  | 7 years    | Move to cold storage|
| Backtest reports               | PostgreSQL  | 5 years    | Move to cold storage|
| LLM call logs                  | Loki        | 90 days    | Delete             |
| Embeddings                     | Qdrant      | 2 years    | Delete             |
| Redis cache                    | Redis       | 30 days    | TTL evict          |

## Cold Storage

- S3 (or equivalent) with lifecycle policy
- Format: Parquet (columnar, queryable with Athena/DuckDB)
- Encryption: AES-256 at rest

## KVKK Compliance

- User PII redacted from logs on ingest
- Right to erasure: hard-delete on user request (cascade)
- Right to export: JSON dump of all user data on request
- Right to explanation: decision trace available < 24h

## Backup Strategy

| Type             | Frequency   | Retention |
|------------------|-------------|-----------|
| Full backup      | Daily 02:00 | 30 days   |
| WAL archive      | Continuous  | 7 days    |
| Qdrant snapshot  | Daily 03:00 | 14 days   |
| Redis RDB        | Every 6h    | 7 days    |

## DR Procedure

1. Restore latest full backup to new PostgreSQL instance
2. Replay WAL up to failure point
3. Restore Qdrant snapshot
4. Restore Redis RDB
5. Verify with smoke test (1 ticker end-to-end)
6. Switch DNS to new instance
7. Total RTO: < 1 hour
