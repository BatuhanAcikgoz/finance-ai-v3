# 10 — Database Overview

> Three stores: PostgreSQL (relational source of truth), Redis (cache + pub/sub + DLQ), Qdrant (vector).

## Store Catalog

| Store       | Purpose                              | Data volume (1yr) | Backup frequency |
|-------------|--------------------------------------|-------------------|------------------|
| PostgreSQL  | Source of truth for all structured   | ~200 GB           | Daily full + WAL |
| Redis       | Cache, pub/sub, streams, DLQ         | ~8 GB             | RDB every 6h     |
| Qdrant      | Vector embeddings (memory)           | ~50 GB            | Daily snapshot   |

## Connection Topology

```
Services → PGBouncer (pool) → PostgreSQL primary (writes)
                          → PostgreSQL replica (reads)
Services → Redis Cluster (3 nodes) → shards
Services → Qdrant (single node, cluster in V2)
```

## Connection Settings

- **PostgreSQL:** `pool_size=20`, `max_overflow=10`, `pool_pre_ping=true`, `statement_timeout=30s`
- **Redis:** connection pool, `socket_timeout=5s`, `socket_keepalive=true`
- **Qdrant:** `timeout=10s`, `retries=3`

## Naming Conventions

| Type            | Convention                              | Example                |
|-----------------|-----------------------------------------|------------------------|
| Table           | snake_case, plural                      | `kap_disclosures`      |
| Column          | snake_case                              | `published_at`         |
| Index           | `idx_{table}_{columns}`                 | `idx_decisions_ticker` |
| Foreign key     | `fk_{table}_{ref_table}`                | `fk_decisions_ticker`  |
| Migration       | `V{YYYYMMDDHHMM}__{description}.sql`    | `V202607281200__add_decisions.py` |
| Redis key       | colon-separated, lowercase              | `tick:thyo:latest`     |
| Qdrant collection | snake_case                            | `news_embeddings`      |
