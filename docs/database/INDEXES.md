# Database Index Strategy

This document provides comprehensive documentation of the database index strategy for the ArbitrageAI project.

## Overview

Database indexes are critical for query performance. Without proper indexes, the database must perform full table scans (O(n) complexity) for every query. With indexes, lookups become O(log n) or even O(1) for unique indexes.

## Index Categories

### 1. Primary Key Indexes (Automatic)
All primary keys are automatically indexed by the database.

### 2. Foreign Key Indexes
Indexes on columns that reference other tables, improving JOIN performance.

### 3. Query Filter Indexes
Indexes on columns frequently used in WHERE clauses.

### 4. Composite Indexes
Multi-column indexes for queries that filter on multiple columns.

### 5. Unique Indexes
Indexes that enforce uniqueness constraints.

---

## Index Inventory by Table

### tasks

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `idx_task_client_email` | client_email | Single | Client-specific queries |
| `idx_task_status` | status | Single | Status filtering |
| `idx_task_created_at` | created_at | Single | Time-based queries |
| `idx_task_client_status` | client_email, status | Composite | Client + status filtering |
| `idx_task_status_created` | status, created_at | Composite | Status + time filtering |
| (inline) | stripe_session_id | Single | Payment lookups |
| (inline) | delivery_token | Single | Delivery lookups |

**Common Query Patterns:**
```sql
-- Uses idx_task_client_email
SELECT * FROM tasks WHERE client_email = 'user@example.com';

-- Uses idx_task_status
SELECT * FROM tasks WHERE status = 'PENDING';

-- Uses idx_task_client_status (composite)
SELECT * FROM tasks WHERE client_email = 'user@example.com' AND status = 'COMPLETED';

-- Uses idx_task_status_created (composite)
SELECT * FROM tasks WHERE status = 'PENDING' ORDER BY created_at DESC;
```

---

### bids

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `idx_bid_posting_id` | job_id | Single | Job lookups |
| `idx_bid_agent_id` | marketplace | Single | Marketplace filtering |
| `idx_bid_status` | status | Single | Status filtering |
| `idx_bid_marketplace_status` | marketplace, status | Composite | Marketplace + status |
| `idx_bid_created_at` | created_at | Single | Time-based queries |

**Common Query Patterns:**
```sql
-- Uses idx_bid_posting_id
SELECT * FROM bids WHERE job_id = 'job_123';

-- Uses idx_bid_marketplace_status (composite)
SELECT * FROM bids WHERE marketplace = 'upwork' AND status = 'PENDING';

-- Uses idx_bid_created_at
SELECT * FROM bids ORDER BY created_at DESC LIMIT 100;
```

---

### client_profiles

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| (unique) | client_email | Unique | User lookups, uniqueness |
| (inline) | client_email | Single | Email filtering |
| (inline) | last_task_at | Single | Recent activity queries |

---

### user_quotas

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `user_id_tier_idx` | user_id, tier | Composite | User tier queries |
| (inline) | user_id | Single | User lookups |

---

### quota_usage

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `user_id_month_idx` | user_id, billing_month | Composite | User period lookups |
| (inline) | user_id | Single | User filtering |
| (inline) | billing_month | Single | Period filtering |

---

### rate_limit_logs

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `user_id_timestamp_idx` | user_id, timestamp | Composite | User time lookups |
| (inline) | user_id | Single | User filtering |
| (inline) | timestamp | Single | Time filtering |

---

### arena_competitions

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| (inline) | task_id | Single | Task lookups |
| (inline) | status | Single | Status filtering |
| (inline) | created_at | Single | Time-based queries |
| (inline) | winner | Single | Winner analysis |

---

### simulation_bids

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `idx_simbid_marketplace` | job_marketplace | Single | Marketplace lookups |
| `idx_simbid_strategy` | strategy_type | Single | Strategy analysis |
| `idx_simbid_outcome` | would_have_won | Single | Outcome analysis |

---

### distributed_locks

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| (inline + unique) | lock_key | Unique | Lock lookups |

---

### scheduled_tasks

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| (inline) | status | Single | Status filtering |
| (inline) | next_run_at | Single | Scheduling queries |

---

### schedule_history

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| (inline) | schedule_id | Single | Schedule lookups |
| (inline) | execution_start | Single | Time-based queries |

---

### escalation_logs

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| (inline) | task_id | Single | Task lookups |
| (inline) | idempotency_key | Single | Idempotency checks |
| (unique) | task_id, idempotency_key | Unique Composite | Prevent duplicates |

---

### threshold_petitions

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `idx_petition_status` | status | Single | Status filtering |
| `idx_petition_created_at` | created_at | Single | Time-based queries |

---

### cost_entries

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `idx_cost_task_id` | task_id | Single | Task cost lookups |
| `idx_cost_bid_id` | bid_id | Single | Bid cost lookups |
| `idx_cost_type` | cost_type | Single | Cost type filtering |
| `idx_cost_marketplace` | marketplace | Single | Marketplace filtering |
| `idx_cost_created_at` | created_at | Single | Time-based queries |

---

### confidence_entries

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `idx_conf_threshold` | threshold | Single | Threshold filtering |
| `idx_conf_won` | won | Single | Win/loss analysis |
| `idx_conf_created_at` | created_at | Single | Time-based queries |

---

### confidence_adjustments

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `idx_conf_adj_reason` | adjustment_reason | Single | Reason analysis |
| `idx_conf_adj_created_at` | created_at | Single | Time-based queries |
| `idx_conf_adj_manual` | is_manual_override | Single | Override filtering |

---

### learning_entries

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `idx_learning_task` | task_id | Single | Task lookups |
| `idx_learning_marketplace` | marketplace | Single | Marketplace filtering |
| `idx_learning_event_type` | event_type | Single | Event type filtering |
| `idx_learning_created_at` | created_at | Single | Time-based queries |

---

### task_executions

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| (inline) | task_id | Single | Task lookups |
| (inline) | status | Single | Status filtering |
| (inline) | started_at | Single | Start time queries |
| (inline) | completed_at | Single | Completion time queries |

---

### task_planning

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| (inline) | task_id | Single | Task lookups |

---

### task_reviews

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| (inline) | task_id | Single | Task lookups |
| (inline) | status | Single | Status filtering |

---

### task_outputs

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| (inline) | task_id | Single | Task lookups |
| (inline) | output_type | Single | Output type filtering |

---

## Migration

Indexes are managed through Alembic migrations. The primary migration for performance indexes is:

**Migration File:** `alembic/versions/001_add_performance_indexes.py`

### Apply Migrations
```bash
python scripts/migrate.py upgrade
```

### Verify Indexes (SQLite)
```bash
sqlite3 data/tasks.db ".indexes"
```

### Verify Indexes (PostgreSQL)
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'tasks';
```

---

## Query Optimization Examples

### Before Index (Full Table Scan)
```sql
EXPLAIN QUERY PLAN SELECT * FROM tasks WHERE client_email = 'user@example.com';
-- Result: SCAN TABLE tasks (full table scan)
```

### After Index (Index Lookup)
```sql
EXPLAIN QUERY PLAN SELECT * FROM tasks WHERE client_email = 'user@example.com';
-- Result: SEARCH TABLE tasks USING INDEX idx_task_client_email (client_email=?)
```

### Composite Index Usage
```sql
-- Uses composite index (client_email, status)
EXPLAIN QUERY PLAN
SELECT * FROM tasks
WHERE client_email = 'user@example.com' AND status = 'COMPLETED';
-- Result: SEARCH TABLE tasks USING INDEX idx_task_client_status (client_email=? AND status=?)
```

---

## Index Maintenance

### When to Add Indexes

1. **Foreign Keys**: Always index columns that reference other tables
2. **WHERE Clauses**: Index columns frequently used in filters
3. **ORDER BY**: Consider indexing columns used for sorting
4. **JOIN Conditions**: Index columns used in join predicates
5. **Composite Queries**: Create composite indexes for multi-column filters

### When NOT to Add Indexes

1. **Low Cardinality**: Columns with few unique values (e.g., boolean flags)
2. **Write-Heavy Tables**: Indexes slow down INSERT/UPDATE/DELETE
3. **Small Tables**: Tables with < 1000 rows rarely benefit from indexes
4. **Redundant Indexes**: Don't create indexes that overlap with existing ones

### Index Redundancy Rules

- `(A, B)` composite index makes single-column index on `A` redundant
- `(A, B, C)` composite index makes `(A, B)` redundant
- Order matters: `(A, B)` is different from `(B, A)`

---

## Performance Benchmarks

| Query Type | Without Index | With Index | Improvement |
|------------|--------------|------------|-------------|
| Task by email (10K rows) | ~500ms | ~5ms | 100x |
| Task by status (10K rows) | ~300ms | ~3ms | 100x |
| Bid by job (5K rows) | ~200ms | ~2ms | 100x |
| Tasks by client+status | ~600ms | ~8ms | 75x |

---

## Monitoring Index Usage

### SQLite
```sql
-- Check if index is being used
EXPLAIN QUERY PLAN SELECT * FROM tasks WHERE client_email = 'test@example.com';
```

### PostgreSQL
```sql
-- Check index usage statistics
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;

-- Find unused indexes
SELECT indexrelname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0;
```

---

## Testing

Index tests are located in `tests/test_database_indexes_issue_38.py`.

### Run Index Tests
```bash
python -m pytest tests/test_database_indexes_issue_38.py -v
```

### Test Coverage
- Index existence verification
- Composite index validation
- Query optimization helper tests
- N+1 query prevention tests
- Index selectivity tests

---

## Related Documentation

- [Migrations Guide](MIGRATIONS.md)
- [Issue QAQC-010](../../.github/ISSUES/QAQC-010-performance-database-indexes.md)
- [Issue QAQC-008](../../.github/ISSUES/QAQC-008-architecture-database-migrations.md)

---

**Last Updated:** March 3, 2026
**Version:** 1.0
**Maintained By:** Development Team
