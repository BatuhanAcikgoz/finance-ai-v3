# 10/04 — Index Strategy

## PostgreSQL Indexes

### Hot path (real-time queries)
| Index                                      | Table                    |
|--------------------------------------------|--------------------------|
| `idx_ticks_ticker_ts`                      | `market_data.ticks`      |
| `idx_bars_ticker_tf_start`                 | `market_data.bars`       |
| `idx_kap_published`                        | `kap.disclosures`        |
| `idx_news_published`                       | `news.articles`          |
| `idx_decisions_portfolio_ticker`           | `decision.decisions`     |

### Filtering
| Index                                      | Table                    |
|--------------------------------------------|--------------------------|
| `idx_kap_material` (partial)               | `kap.disclosures`        |
| `idx_decisions_compliance`                 | `decision.decisions`     |
| `idx_decisions_confidence` (partial)       | `decision.decisions`     |

### GIN (JSONB)
| Index                                      | Table                    |
|--------------------------------------------|--------------------------|
| `idx_decisions_evidence_gin`               | `decision.decisions`     |
| `idx_audit_violations_gin`                 | `audit.compliance_audits`|

## Partitioning

- `market_data.ticks` partitioned by month (drop old partitions > 13 months)
- `market_data.bars` partitioned by month
- `audit.compliance_audits` partitioned by quarter

## Vacuum Strategy

- `autovacuum` enabled with aggressive settings on hot tables
- Manual `VACUUM ANALYZE` weekly on `decision.decisions`
- `pg_repack` quarterly to remove bloat
