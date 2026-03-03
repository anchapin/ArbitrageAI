---
created: 2026-03-03
priority: MEDIUM
qaqc_section: 5.3
estimated_effort: 3 days
target_milestone: Phase 4 - Week 7-8
---

# [PERFORMANCE] Fix N+1 Query Problems with Eager Loading

## ⚡ Performance Issue - Database Query Optimization

**Priority:** MEDIUM  
**Labels:** performance, database, sqlalchemy, qaqc-review, n-plus-one  
**QA/QC Review Reference:** Section 5.3 - N+1 Query Problems

---

## 📍 Location

- **Files:** API endpoints throughout `src/api/`
- **Specific Files:**
  - `src/api/main.py` - Multiple endpoints
  - `src/api/analytics.py` - Analytics queries
  - `src/api/admin_quotas.py` - Admin queries
- **Component:** Database Access Layer

---

## 🐛 Issue Description

Multiple API endpoints suffer from **N+1 query problems**, where:
1. One query fetches a list of records
2. N additional queries fetch related data for each record

**Example Pattern (found in codebase):**
```python
# Anti-pattern: N+1 query
@app.get("/api/tasks")
async def get_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).all()  # 1 query
    
    result = []
    for task in tasks:
        # N additional queries (one per task!)
        bids = db.query(Bid).filter(Bid.task_id == task.id).all()
        result.append({
            "task": task.to_dict(),
            "bids": [bid.to_dict() for bid in bids],
        })
    
    return result
# Total queries: 1 + N (where N = number of tasks)
```

**Impact:**
- 100 tasks = 101 queries instead of 2
- 1000 tasks = 1001 queries instead of 2
- Causes database overload
- Slow API responses (100ms → 5000ms)

---

## ⚠️ Risk Assessment

- **Severity:** Medium (performance degradation)
- **Impact:** Database overload, slow responses, timeouts
- **Likelihood:** High (occurs on every list endpoint)
- **Performance:** Severe (linear query growth)

---

## 🎯 Acceptance Criteria

- [ ] All N+1 queries identified
- [ ] Eager loading implemented with `joinedload()` and `selectinload()`
- [ ] Query count reduced by 90%+
- [ ] API response times improved
- [ ] All tests passing
- [ ] No regression in functionality

---

## 🔧 Implementation Notes

### Solution: SQLAlchemy Eager Loading

#### Pattern 1: `joinedload()` for One-to-One/One-to-Many

```python
# Before (N+1 queries)
@app.get("/api/tasks")
async def get_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    result = []
    for task in tasks:
        client = db.query(ClientProfile).filter(
            ClientProfile.client_email == task.client_email
        ).first()  # N queries!
        result.append({"task": task, "client": client})
    return result

# After (2 queries with joinedload)
from sqlalchemy.orm import joinedload

@app.get("/api/tasks")
async def get_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).options(
        joinedload(Task.client_profile)  # Eager load relationship
    ).all()
    
    result = []
    for task in tasks:
        # No additional query - client_profile already loaded
        result.append({
            "task": task,
            "client": task.client_profile,
        })
    return result
```

#### Pattern 2: `selectinload()` for Collections

```python
# Before (N+1 queries)
@app.get("/api/tasks/{task_id}/bids")
async def get_task_bids(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    bids = []
    for bid in task.bids:  # N queries for bid details!
        bid_details = db.query(Bid).filter(Bid.id == bid.id).first()
        bids.append(bid_details)
    return bids

# After (2 queries with selectinload)
from sqlalchemy.orm import selectinload

@app.get("/api/tasks/{task_id}/bids")
async def get_task_bids(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).options(
        selectinload(Task.bids)  # Eager load collection
    ).filter(Task.id == task_id).first()
    
    return task.bids  # Already loaded
```

#### Pattern 3: Multiple Levels of Relationships

```python
# Before (1 + N + N*M queries!)
@app.get("/api/admin/tasks")
async def get_all_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    result = []
    for task in tasks:
        # N queries
        bids = db.query(Bid).filter(Bid.task_id == task.id).all()
        bid_data = []
        for bid in bids:
            # N*M queries
            bidder = db.query(User).filter(User.id == bid.user_id).first()
            bid_data.append({"bid": bid, "bidder": bidder})
        result.append({"task": task, "bids": bid_data})
    return result

# After (3 queries total!)
from sqlalchemy.orm import joinedload, selectinload

@app.get("/api/admin/tasks")
async def get_all_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).options(
        selectinload(Task.bids).joinedload(Bid.bidder)  # Chain loaders
    ).all()
    
    return [
        {
            "task": task,
            "bids": [
                {"bid": bid, "bidder": bid.bidder}
                for bid in task.bids
            ],
        }
        for task in tasks
    ]
```

### Specific Fixes for ArbitrageAI

#### Fix 1: Task List Endpoint

```python
# src/api/main.py

from sqlalchemy.orm import joinedload, selectinload

@app.get("/api/tasks")
async def list_tasks(
    status: Optional[str] = None,
    client_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List tasks with eager loading to avoid N+1 queries."""
    query = db.query(Task).options(
        joinedload(Task.client_profile),
        selectinload(Task.bids),
    )
    
    if status:
        query = query.filter(Task.status == status)
    
    if client_email:
        query = query.filter(Task.client_email == client_email)
    
    tasks = query.all()
    
    return [
        {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "amount_paid": task.amount_paid,
            "client_email": task.client_email,
            "bids_count": len(task.bids),
        }
        for task in tasks
    ]
```

#### Fix 2: Client Dashboard

```python
# src/api/main.py

@app.get("/api/client/history")
async def get_client_history(
    request: Request,
    db: Session = Depends(get_db),
):
    """Get client task history with eager loading."""
    from ..utils.client_auth import get_client_email_from_request
    
    client_email = get_client_email_from_request(request)
    
    tasks = db.query(Task).options(
        selectinload(Task.bids),
        selectinload(Task.escalation_logs),
    ).filter(
        Task.client_email == client_email
    ).order_by(Task.created_at.desc()).all()
    
    return [
        {
            "id": task.id,
            "title": task.title,
            "domain": task.domain,
            "status": task.status,
            "amount_paid": task.amount_paid,
            "bids_count": len(task.bids),
            "has_escalations": len(task.escalation_logs) > 0,
            "created_at": task.created_at.isoformat(),
        }
        for task in tasks
    ]
```

#### Fix 3: Admin Analytics

```python
# src/api/analytics.py

from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import func

@app.get("/api/admin/metrics")
async def get_admin_metrics(db: Session = Depends(get_db)):
    """Get admin metrics with optimized queries."""
    
    # Use aggregate queries instead of loading all records
    total_tasks = db.query(func.count(Task.id)).scalar()
    completed_tasks = db.query(func.count(Task.id)).filter(
        Task.status == TaskStatus.COMPLETED
    ).scalar()
    
    # Get recent tasks with eager loading
    recent_tasks = db.query(Task).options(
        selectinload(Task.bids),
    ).order_by(
        Task.created_at.desc()
    ).limit(10).all()
    
    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "completion_rate": completed_tasks / total_tasks if total_tasks > 0 else 0,
        "recent_tasks": [
            {
                "id": task.id,
                "status": task.status,
                "bids_count": len(task.bids),
            }
            for task in recent_tasks
        ],
    }
```

---

## 📋 Testing Requirements

### Query Count Tests:
```python
# tests/test_n_plus_one.py

import pytest
from sqlalchemy.orm import Session
from pytest import LogCaptureFixture

def test_task_list_no_n_plus_one(caplog: LogCaptureFixture):
    """Test that task list endpoint doesn't have N+1 queries."""
    from src.api.main import list_tasks
    from src.api.database import get_db
    
    # Create test data
    db: Session = next(get_db())
    try:
        # Insert 10 tasks
        for i in range(10):
            task = Task(id=f"test_{i}", client_email="test@example.com")
            db.add(task)
        db.commit()
        
        # Capture SQL queries
        with caplog.at_level(logging.DEBUG):
            response = list_tasks(db=db)
        
        # Count SELECT queries
        select_count = sum(1 for msg in caplog.messages if "SELECT" in msg)
        
        # Should be 1 query, not 11 (1 + N)
        assert select_count <= 2, f"Too many queries: {select_count}"
        
    finally:
        db.rollback()
        db.execute(text("DELETE FROM tasks WHERE client_email = 'test@example.com'"))
        db.commit()
        db.close()
```

### Performance Tests:
```python
# tests/benchmarks/test_eager_loading.py

@pytest.mark.benchmark
def test_task_list_performance(benchmark):
    """Benchmark task list endpoint performance."""
    from src.api.main import list_tasks
    from src.api.database import get_db
    
    db = next(get_db())
    
    def query():
        return list_tasks(db=db)
    
    # Should complete in <100ms even with 1000 tasks
    result = benchmark(query)
    assert len(result) > 0
    
    db.close()
```

---

## 📊 Expected Performance Improvements

| Endpoint | Before (N+1) | After (Eager) | Improvement |
|----------|-------------|---------------|-------------|
| GET /api/tasks (100) | 101 queries, 2000ms | 2 queries, 50ms | 40x |
| GET /api/client/history | 51 queries, 1500ms | 2 queries, 40ms | 37x |
| GET /api/admin/metrics | 201 queries, 3000ms | 5 queries, 80ms | 37x |

---

## 📚 References

- **QA/QC Review:** Deep QA/QC Review - March 2026, Section 5.3
- **SQLAlchemy Loading Strategies:** https://docs.sqlalchemy.org/en/20/orm/loading_relationships.html
- **Eager Loading:** https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#eager-loading
- **Related Issues:** QAQC-010 (Database indexes)

---

## 🎯 Success Metrics

- [ ] Zero N+1 queries in critical paths
- [ ] Query count reduced by 90%+
- [ ] API response times <100ms for list endpoints
- [ ] All tests passing
- [ ] Database CPU usage reduced

---

## 📝 Additional Notes

### Detection Tools:
```python
# Add to development configuration
# Log all queries to detect N+1 patterns

import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

### Code Review Checklist:
- [ ] No loops with database queries inside
- [ ] `joinedload()` used for one-to-one relationships
- [ ] `selectinload()` used for collections
- [ ] Aggregate functions used instead of loading all records
- [ ] Query count verified in tests

---

**Created from:** Deep QA/QC Review - March 3, 2026  
**Issue Template:** qaqc-performance.md
