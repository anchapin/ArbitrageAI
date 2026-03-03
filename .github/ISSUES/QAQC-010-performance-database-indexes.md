---
created: 2026-03-03
priority: MEDIUM
qaqc_section: 5.2
estimated_effort: 4 days
target_milestone: Phase 4 - Week 7-8
---

# [PERFORMANCE] Add Database Indexes for Frequently Queried Fields

## ⚡ Performance Issue - Database Optimization

**Priority:** MEDIUM  
**Labels:** performance, database, indexes, qaqc-review, sqlalchemy  
**QA/QC Review Reference:** Section 5.2 - Missing Database Indexes

---

## 📍 Location

- **Files:**
  - `src/api/models.py` - SQLAlchemy model definitions
  - `src/api/migrations/` - Migration scripts (after QAQC-008)
- **Tables:** tasks, bids, client_profiles, arena_competitions, escalation_logs
- **Component:** Database Layer

---

## 🐛 Issue Description

The database models lack indexes on frequently queried fields, causing:

1. **Full Table Scans:** Every query scans entire tables
2. **Slow Lookups:** O(n) instead of O(log n) performance
3. **Poor JOIN Performance:** Foreign keys without indexes
4. **Timeout Risk:** Large tables will cause query timeouts
5. **Scaling Issues:** Performance degrades linearly with data growth

Current state (from `models.py`):
```python
class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True)  # ✅ Indexed (PK)
    client_email = Column(String, nullable=True)  # ❌ No index
    status = Column(String, default=TaskStatus.PENDING)  # ❌ No index
    created_at = Column(DateTime, default=datetime.utcnow)  # ❌ No index
    amount_paid = Column(Integer, default=0)  # ❌ No index
    # ... many more unindexed fields
```

---

## ⚠️ Risk Assessment

- **Severity:** Medium (performance degradation)
- **Impact:** Query timeouts, slow API responses
- **Likelihood:** High (will occur as data grows)
- **Performance:** Severe (exponential slowdown with data growth)

---

## 🎯 Acceptance Criteria

- [ ] All foreign keys indexed
- [ ] All frequently-queried fields indexed
- [ ] Composite indexes for common query patterns
- [ ] Migration created for production
- [ ] Query performance benchmarks improved
- [ ] No regression in write performance

---

## 🔧 Implementation Notes

### Index Priority Analysis

#### Critical Indexes (Create Immediately):

```python
# src/api/models.py

class Task(Base):
    __tablename__ = "tasks"
    
    # ... existing columns ...
    
    # Add indexes:
    __table_args__ = (
        # Foreign key indexes
        Index('ix_tasks_client_email', 'client_email'),
        Index('ix_tasks_session_id', 'session_id'),
        
        # Query filter indexes
        Index('ix_tasks_status', 'status'),
        Index('ix_tasks_created_at', 'created_at'),
        Index('ix_tasks_updated_at', 'updated_at'),
        
        # Composite indexes for common queries
        Index('ix_tasks_status_created', 'status', 'created_at'),
        Index('ix_tasks_client_status', 'client_email', 'status'),
        
        # Unique constraints (also create indexes)
        UniqueConstraint('id', name='uq_tasks_id'),
    )
```

#### High Priority Indexes:

```python
class Bid(Base):
    __tablename__ = "bids"
    
    # ... columns ...
    
    __table_args__ = (
        # Foreign keys
        Index('ix_bids_task_id', 'task_id'),
        Index('ix_bids_job_id', 'job_id'),
        
        # Query filters
        Index('ix_bids_status', 'status'),
        Index('ix_bids_created_at', 'created_at'),
        Index('ix_bids_marketplace', 'marketplace'),
        
        # Composite
        Index('ix_bids_status_created', 'status', 'created_at'),
    )


class ClientProfile(Base):
    __tablename__ = "client_profiles"
    
    # ... columns ...
    
    __table_args__ = (
        UniqueConstraint('client_email', name='uq_client_profiles_email'),
        Index('ix_client_profiles_email', 'client_email'),  # Already unique, but explicit
    )


class ArenaCompetition(Base):
    __tablename__ = "arena_competitions"
    
    # ... columns ...
    
    __table_args__ = (
        Index('ix_arena_competitions_task_id', 'task_id'),
        Index('ix_arena_competitions_status', 'status'),
        Index('ix_arena_competitions_created_at', 'created_at'),
    )


class EscalationLog(Base):
    __tablename__ = "escalation_logs"
    
    # ... columns ...
    
    __table_args__ = (
        Index('ix_escalation_logs_task_id', 'task_id'),
        Index('ix_escalation_logs_idempotency_key', 'idempotency_key'),
        Index('ix_escalation_logs_created_at', 'created_at'),
    )
```

### Migration Script

```python
# alembic/versions/002_add_database_indexes.py
"""Add database indexes for performance

Revision ID: def456
Revises: abc123
Create Date: 2026-03-03

"""
from alembic import op

# revision identifiers
revision = 'def456'
down_revision = 'abc123'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tasks table indexes
    op.create_index('ix_tasks_client_email', 'tasks', ['client_email'])
    op.create_index('ix_tasks_session_id', 'tasks', ['session_id'])
    op.create_index('ix_tasks_status', 'tasks', ['status'])
    op.create_index('ix_tasks_created_at', 'tasks', ['created_at'])
    op.create_index('ix_tasks_updated_at', 'tasks', ['updated_at'])
    op.create_index('ix_tasks_status_created', 'tasks', ['status', 'created_at'])
    op.create_index('ix_tasks_client_status', 'tasks', ['client_email', 'status'])
    
    # Bids table indexes
    op.create_index('ix_bids_task_id', 'bids', ['task_id'])
    op.create_index('ix_bids_job_id', 'bids', ['job_id'])
    op.create_index('ix_bids_status', 'bids', ['status'])
    op.create_index('ix_bids_created_at', 'bids', ['created_at'])
    op.create_index('ix_bids_marketplace', 'bids', ['marketplace'])
    op.create_index('ix_bids_status_created', 'bids', ['status', 'created_at'])
    
    # Arena competitions indexes
    op.create_index('ix_arena_competitions_task_id', 'arena_competitions', ['task_id'])
    op.create_index('ix_arena_competitions_status', 'arena_competitions', ['status'])
    op.create_index('ix_arena_competitions_created_at', 'arena_competitions', ['created_at'])
    
    # Escalation logs indexes
    op.create_index('ix_escalation_logs_task_id', 'escalation_logs', ['task_id'])
    op.create_index('ix_escalation_logs_idempotency_key', 'escalation_logs', ['idempotency_key'])
    op.create_index('ix_escalation_logs_created_at', 'escalation_logs', ['created_at'])


def downgrade() -> None:
    # Tasks table indexes
    op.drop_index('ix_tasks_client_status', table_name='tasks')
    op.drop_index('ix_tasks_status_created', table_name='tasks')
    op.drop_index('ix_tasks_updated_at', table_name='tasks')
    op.drop_index('ix_tasks_created_at', table_name='tasks')
    op.drop_index('ix_tasks_status', table_name='tasks')
    op.drop_index('ix_tasks_session_id', table_name='tasks')
    op.drop_index('ix_tasks_client_email', table_name='tasks')
    
    # Bids table indexes
    op.drop_index('ix_bids_status_created', table_name='bids')
    op.drop_index('ix_bids_marketplace', table_name='bids')
    op.drop_index('ix_bids_created_at', table_name='bids')
    op.drop_index('ix_bids_status', table_name='bids')
    op.drop_index('ix_bids_job_id', table_name='bids')
    op.drop_index('ix_bids_task_id', table_name='bids')
    
    # Arena competitions indexes
    op.drop_index('ix_arena_competitions_created_at', table_name='arena_competitions')
    op.drop_index('ix_arena_competitions_status', table_name='arena_competitions')
    op.drop_index('ix_arena_competitions_task_id', table_name='arena_competitions')
    
    # Escalation logs indexes
    op.drop_index('ix_escalation_logs_created_at', table_name='escalation_logs')
    op.drop_index('ix_escalation_logs_idempotency_key', table_name='escalation_logs')
    op.drop_index('ix_escalation_logs_task_id', table_name='escalation_logs')
```

### Update SQLAlchemy Models

```python
# src/api/models.py - Updated Task model

class Task(Base):
    """Task model with optimized indexes."""
    
    __tablename__ = "tasks"
    
    __table_args__ = (
        # Foreign key indexes
        Index('ix_tasks_client_email', 'client_email'),
        Index('ix_tasks_session_id', 'session_id'),
        
        # Query filter indexes
        Index('ix_tasks_status', 'status'),
        Index('ix_tasks_created_at', 'created_at'),
        Index('ix_tasks_updated_at', 'updated_at'),
        
        # Composite indexes for common queries
        Index('ix_tasks_status_created', 'status', 'created_at'),
        Index('ix_tasks_client_status', 'client_email', 'status'),
        
        # Unique constraints
        UniqueConstraint('id', name='uq_tasks_id'),
    )
    
    # ... rest of columns unchanged ...
```

---

## 📋 Testing Requirements

### Performance Tests:
```python
# tests/test_database_indexes.py

import time
from sqlalchemy import text

def test_task_query_performance_with_index():
    """Test that task queries use indexes."""
    from src.api.database import SessionLocal, engine
    from src.api.models import Task
    
    # Create test data
    db = SessionLocal()
    try:
        # Insert 1000 test tasks
        for i in range(1000):
            task = Task(
                id=f"test_task_{i}",
                client_email=f"test{i}@example.com",
                status="PENDING",
            )
            db.add(task)
        db.commit()
        
        # Query with index
        start = time.time()
        tasks = db.query(Task).filter(
            Task.client_email == "test500@example.com"
        ).all()
        duration_with_index = time.time() - start
        
        # Verify index is used (EXPLAIN ANALYZE)
        result = db.execute(text(
            "EXPLAIN QUERY PLAN SELECT * FROM tasks WHERE client_email = :email"
        ), {"email": "test500@example.com"})
        plan = result.fetchone()[0]
        
        # Should use INDEX or SEARCH, not SCAN
        assert "SCAN" not in plan or "USING INDEX" in plan
        
        # Query should be fast (<10ms for indexed lookup)
        assert duration_with_index < 0.01
        
    finally:
        db.rollback()
        # Cleanup
        db.execute(text("DELETE FROM tasks WHERE client_email LIKE 'test%@example.com'"))
        db.commit()
        db.close()
```

### Benchmark Tests:
```python
# tests/benchmarks/test_query_benchmarks.py

import pytest
from sqlalchemy import text

@pytest.mark.benchmark
def test_task_status_query_benchmark(benchmark):
    """Benchmark task status queries."""
    from src.api.database import SessionLocal
    from src.api.models import Task
    
    db = SessionLocal()
    
    def query():
        return db.query(Task).filter(Task.status == "PENDING").limit(100).all()
    
    # Should complete in <50ms
    result = benchmark(query)
    assert len(result) <= 100
    
    db.close()
```

---

## 📊 Expected Performance Improvements

| Query Type | Before (no index) | After (indexed) | Improvement |
|------------|------------------|-----------------|-------------|
| Task by email | ~500ms (10K rows) | ~5ms | 100x |
| Task by status | ~300ms (10K rows) | ~3ms | 100x |
| Bid by job | ~200ms (5K rows) | ~2ms | 100x |
| Tasks by client+status | ~600ms | ~8ms | 75x |

---

## 📚 References

- **QA/QC Review:** Deep QA/QC Review - March 2026, Section 5.2
- **SQLAlchemy Indexes:** https://docs.sqlalchemy.org/en/20/core/constraints.html#indexes
- **Alembic:** https://alembic.sqlalchemy.org/
- **PostgreSQL Indexes:** https://www.postgresql.org/docs/current/indexes.html
- **Related Issues:** QAQC-008 (Database migrations), QAQC-011 (N+1 queries)

---

## 🎯 Success Metrics

- [ ] All critical queries use indexes
- [ ] Query performance <10ms for single-row lookups
- [ ] Query performance <50ms for filtered lists
- [ ] EXPLAIN plans show index usage
- [ ] No full table scans on large tables

---

## 📝 Additional Notes

### Index Creation Order:
1. Create migrations framework (QAQC-008)
2. Add foreign key indexes
3. Add query filter indexes
4. Add composite indexes
5. Monitor and optimize

### Monitoring:
```sql
-- Check index usage (PostgreSQL)
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;

-- Find missing indexes (queries with full table scans)
EXPLAIN ANALYZE SELECT * FROM tasks WHERE client_email = 'test@example.com';
```

---

**Created from:** Deep QA/QC Review - March 3, 2026  
**Issue Template:** qaqc-performance.md
