---
created: 2026-03-03
priority: HIGH
qaqc_section: 2.1
estimated_effort: 10 days
target_milestone: Phase 2 - Week 3-4
---

# [CODE QUALITY] Refactor Monolithic Files (>1000 Lines)

## 📁 Code Quality Issue - Maintainability

**Priority:** HIGH  
**Labels:** code-quality, refactoring, maintainability, qaqc-review  
**QA/QC Review Reference:** Section 2.1 - Massive File Sizes

---

## 📍 Location

- **Primary Files:**
  - `src/api/main.py` - **4,103 lines** (CRITICAL)
  - `src/agent_execution/executor.py` - **3,655 lines** (CRITICAL)
- **Secondary Files:**
  - `src/agent_execution/market_scanner.py` - 1,309 lines
  - `src/api/models.py` - 1,903 lines
  - `src/utils/health_check.py` - 698 lines (approaching limit)
  - `src/utils/logging_alerting.py` - 648 lines (approaching limit)
- **Component:** Core Application Logic

---

## 🐛 Issue Description

Several files in the codebase have grown to unmanageable sizes:

| File | Lines | Max Recommended | Over By |
|------|-------|-----------------|---------|
| `main.py` | 4,103 | 500 | 3,603 lines |
| `executor.py` | 3,655 | 500 | 3,155 lines |
| `market_scanner.py` | 1,309 | 500 | 809 lines |
| `models.py` | 1,903 | 500 | 1,403 lines |

**Problems:**
1. **Difficult to Review:** PRs touching these files are huge
2. **Merge Conflicts:** Multiple developers working on same file
3. **Cognitive Load:** Too many responsibilities in one file
4. **Testing Difficulty:** Hard to test individual concerns
5. **Bug Risk:** Changes have wide blast radius

---

## ⚠️ Risk Assessment

- **Severity:** High (maintainability crisis)
- **Impact:** Slow development, high bug rate, team frustration
- **Likelihood:** Certain (already experiencing issues)
- **Technical Debt:** Severe

---

## 🎯 Acceptance Criteria

- [ ] `main.py` split into multiple focused modules (max 500 lines each)
- [ ] `executor.py` split into multiple focused modules (max 500 lines each)
- [ ] All tests passing after refactoring
- [ ] No regression in functionality
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Import paths updated throughout codebase

---

## 🔧 Implementation Notes

### Refactoring Plan for `main.py` (4,103 lines)

#### Current Structure Analysis:
```
src/api/main.py (4,103 lines)
├── Imports (lines 1-100)
├── Configuration (lines 101-200)
├── Rate Limiting (lines 201-400)
├── Authentication (lines 401-600)
├── Checkout Endpoints (lines 601-900)
├── Task Management Endpoints (lines 901-1400)
├── Payment Webhooks (lines 1401-1800)
├── Client Dashboard Endpoints (lines 1801-2200)
├── Admin Endpoints (lines 2201-2600)
├── Arena Competition Endpoints (lines 2601-3000)
├── WebSocket Handlers (lines 3001-3400)
├── Background Tasks (lines 3401-3700)
└── Utility Functions (lines 3701-4103)
```

#### Proposed New Structure:
```
src/api/
├── main.py (100 lines) - App initialization and routing only
├── __init__.py
├── routes/
│   ├── __init__.py
│   ├── checkout.py (300 lines) - Checkout session endpoints
│   ├── tasks.py (400 lines) - Task management endpoints
│   ├── webhooks.py (300 lines) - Payment webhook handlers
│   ├── client_dashboard.py (300 lines) - Client-facing endpoints
│   ├── admin.py (300 lines) - Admin endpoints
│   ├── arena.py (300 lines) - Arena competition endpoints
│   └── websocket.py (300 lines) - WebSocket handlers
├── middleware/
│   ├── __init__.py
│   ├── rate_limit.py (200 lines) - Rate limiting middleware
│   ├── auth.py (200 lines) - Authentication middleware
│   └── security_headers.py (100 lines) - Security headers
├── dependencies/
│   ├── __init__.py
│   ├── database.py (100 lines) - DB dependencies
│   ├── auth.py (100 lines) - Auth dependencies
│   └── quotas.py (150 lines) - Quota management
└── schemas/
    ├── __init__.py
    ├── checkout.py (100 lines) - Checkout request/response schemas
    ├── tasks.py (150 lines) - Task schemas
    └── admin.py (100 lines) - Admin schemas
```

#### Example: Extract Checkout Routes

**Before (in main.py):**
```python
@app.post("/api/create-checkout-session")
async def create_checkout_session(
    request: CheckoutRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    # 200+ lines of checkout logic
    ...

@app.get("/api/checkout/status/{session_id}")
async def checkout_status(
    session_id: str,
    db: Session = Depends(get_db),
):
    # 100+ lines of status logic
    ...
```

**After (in routes/checkout.py):**
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..dependencies import get_db, get_current_user
from ..schemas import CheckoutRequest, CheckoutResponse

router = APIRouter(prefix="/api", tags=["checkout"])

@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CheckoutRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> CheckoutResponse:
    """Create a new checkout session."""
    # Same logic, but in focused module
    ...

@router.get("/checkout/status/{session_id}")
async def checkout_status(
    session_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Get checkout session status."""
    ...
```

**Updated main.py:**
```python
from fastapi import FastAPI
from .routes import checkout, tasks, webhooks, client_dashboard, admin, arena, websocket
from .middleware import setup_middleware

def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(title="ArbitrageAI")
    
    # Setup middleware
    setup_middleware(app)
    
    # Include routers
    app.include_router(checkout.router)
    app.include_router(tasks.router)
    app.include_router(webhooks.router)
    app.include_router(client_dashboard.router)
    app.include_router(admin.router)
    app.include_router(arena.router)
    app.include_router(websocket.router)
    
    return app

app = create_app()
```

### Refactoring Plan for `executor.py` (3,655 lines)

#### Current Structure:
```
src/agent_execution/executor.py
├── Configuration (lines 1-100)
├── TaskRouter Class (lines 101-800)
├── Visualization Handler (lines 801-1400)
├── Document Generator (lines 1401-2000)
├── Spreadsheet Generator (lines 2001-2600)
├── Report Generator (lines 2601-3000)
├── Code Execution (lines 3001-3400)
└── Review & Retry Logic (lines 3401-3655)
```

#### Proposed New Structure:
```
src/agent_execution/
├── executor.py (200 lines) - Main orchestration only
├── __init__.py
├── task_router.py (300 lines) - Task routing logic
├── handlers/
│   ├── __init__.py
│   ├── visualization.py (400 lines) - Chart/image generation
│   ├── document.py (400 lines) - Document generation
│   ├── spreadsheet.py (400 lines) - Excel generation
│   └── report.py (300 lines) - Report generation
├── code_execution.py (400 lines) - Sandbox execution
└── review.py (300 lines) - Review and retry logic
```

---

## 📋 Testing Strategy

### Before Refactoring:
```bash
# Run all tests and save results
pytest tests/ -v --tb=short > tests_before.txt
```

### After Each Refactoring Step:
```bash
# Run tests to ensure no regression
pytest tests/ -v --tb=short > tests_after_step.txt
diff tests_before.txt tests_after_step.txt
```

### Integration Tests:
```python
# tests/test_refactoring.py

def test_main_app_initialization():
    """Test that app initializes correctly after refactoring."""
    from src.api.main import app
    
    assert app is not None
    assert len(app.routes) > 0

def test_all_endpoints_accessible():
    """Test that all endpoints are still accessible."""
    from src.api.main import app
    
    expected_routes = [
        "/api/create-checkout-session",
        "/api/tasks/{task_id}",
        "/api/webhook",
        # ... all other routes
    ]
    
    route_paths = [route.path for route in app.routes]
    
    for expected in expected_routes:
        assert any(expected in path for path in route_paths)
```

---

## 📊 Progress Tracking

### Phase 1: main.py Refactoring (5 days)
- [ ] Day 1: Analyze and plan extraction
- [ ] Day 2: Extract routes to separate modules
- [ ] Day 3: Extract middleware
- [ ] Day 4: Extract dependencies and schemas
- [ ] Day 5: Testing and documentation

### Phase 2: executor.py Refactoring (5 days)
- [ ] Day 1: Analyze and plan extraction
- [ ] Day 2: Extract TaskRouter
- [ ] Day 3: Extract handlers
- [ ] Day 4: Extract code execution and review
- [ ] Day 5: Testing and documentation

---

## 📚 References

- **QA/QC Review:** Deep QA/QC Review - March 2026, Section 2.1
- **Clean Code:** Robert C. Martin - Chapter on Functions and Modules
- **Refactoring:** Martin Fowler - Extract Module pattern
- **FastAPI:** [Modular API Structure](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

---

## 🎯 Success Metrics

- [ ] All files under 500 lines (except models.py which needs separate issue)
- [ ] Average file size: <400 lines
- [ ] Code coverage maintained or improved
- [ ] Developer satisfaction survey: improved
- [ ] PR review time reduced by 50%

---

## 📝 Additional Notes

### Git Strategy:
1. Create feature branch: `refactor/monolithic-files`
2. Make small, incremental commits
3. Test after each extraction
4. Squash commits before merging

### Code Review Guidelines:
- Review each extracted module separately
- Verify no circular dependencies
- Check import paths are correct
- Ensure documentation is updated

### Rollback Plan:
If issues are discovered:
1. Revert the problematic commit
2. Fix the issue in isolation
3. Re-apply the refactoring
4. Test thoroughly

---

**Created from:** Deep QA/QC Review - March 3, 2026  
**Issue Template:** qaqc-code-quality.md
