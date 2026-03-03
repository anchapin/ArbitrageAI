---
created: 2026-03-03
priority: MEDIUM
qaqc_section: 2.2
estimated_effort: 5 days
target_milestone: Phase 2 - Week 3-4
---

# [CODE QUALITY] Fix All Ruff Linting Violations

## 🐛 Code Quality Issue - Comprehensive Linting

**Priority:** MEDIUM  
**Labels:** code-quality, linting, qaqc-review, ruff  
**QA/QC Review Reference:** Section 2.2 - Ruff Linting Violations

---

## 📍 Location

- **Files:** Throughout `src/` directory
- **Ruff Rules:** Multiple (see breakdown below)
- **Total Violations:** ~2,500+
- **Component:** Entire codebase

---

## 🐛 Issue Description

The codebase has **~2,500+ ruff linting violations** across multiple rule categories:

| Rule | Count | Description | Auto-fixable |
|------|-------|-------------|--------------|
| COM812 | 847 | missing-trailing-comma | ✅ Yes |
| W293 | 521 | blank-line-with-whitespace | ✅ Yes |
| UP006 | 478 | non-pep585-annotation | ✅ Yes |
| UP045 | 386 | non-pep604-optional | ✅ Yes |
| B904 | 157 | raise-without-from | ❌ Manual |
| PLR6301 | 142 | no-self-use | ❌ Manual |
| PLC0415 | 133 | import-outside-top-level | ❌ Manual |
| D415 | 126 | missing-terminal-punctuation | ✅ Yes |
| RUF010 | 115 | explicit-f-string-conversion | ✅ Yes |
| UP099 | 99 | deprecated-import | ✅ Yes |
| TID252 | 92 | relative-imports | ❌ Manual |
| I001 | 83 | unsorted-imports | ✅ Yes |
| DTZ003 | 69 | call-datetime-utcnow | ❌ Manual |
| RET505 | 56 | superfluous-else-return | ❌ Manual |
| D102 | 53 | undocumented-public-method | ❌ Manual |
| B008 | 51 | function-call-in-default | ❌ Manual |
| F821 | 50 | undefined-name | ❌ Manual |
| PLW0603 | 50 | global-statement | ❌ Manual |
| *Other* | ~300 | Various rules | Mixed |

---

## ⚠️ Risk Assessment

- **Severity:** Medium (code quality and maintainability)
- **Impact:** Slower development, harder onboarding
- **Likelihood:** Certain (affects all developers)
- **Technical Debt:** High

---

## 🎯 Acceptance Criteria

- [ ] All auto-fixable violations fixed
- [ ] Manual violations addressed or documented
- [ ] Ruff check passes with zero errors
- [ ] Ruff check warnings reduced by 90%+
- [ ] Pre-commit hooks updated
- [ ] CI/CD validation added
- [ ] All tests passing

---

## 🔧 Implementation Notes

### Phase 1: Auto-Fixable Violations (2 days)

Run ruff's auto-fix on all fixable issues:

```bash
# Fix all auto-fixable violations
ruff check src/ --fix

# Format code (fixes COM812, W293, etc.)
ruff format src/

# Check remaining issues
ruff check src/ --statistics
```

### Phase 2: Type Annotation Updates (1 day)

Update type annotations to modern Python 3.10+ syntax:

```python
# Before (PEP 585)
from typing import List, Dict, Optional

def process(items: List[str], mapping: Dict[str, int]) -> Optional[str]:
    ...

# After (PEP 585)
def process(items: list[str], mapping: dict[str, int]) -> str | None:
    ...
```

### Phase 3: Import Organization (1 day)

Fix import sorting and style:

```bash
# Sort imports automatically
ruff check src/ --select I001 --fix
```

Ensure imports follow project convention:
```python
# Standard library
import os
import json
from datetime import datetime

# Third-party
import fastapi
import sqlalchemy

# Local imports
from src.api import models
from ..utils import logger
```

### Phase 4: Manual Fixes (1 day)

Address remaining manual violations:

#### PLR6301 (no-self-use):
```python
# Before
class MyClass:
    def utility_method(self, arg1, arg2):  # Doesn't use self
        return arg1 + arg2

# After
class MyClass:
    @staticmethod
    def utility_method(arg1, arg2):
        return arg1 + arg2
```

#### PLC0415 (import-outside-top-level):
```python
# Before
def my_function():
    import heavy_module  # Import inside function
    heavy_module.do_something()

# After
import heavy_module  # Top-level import

def my_function():
    heavy_module.do_something()
```

#### DTZ003 (call-datetime-utcnow):
```python
# Before
from datetime import datetime
now = datetime.utcnow()  # Naive datetime

# After
from datetime import datetime, timezone
now = datetime.now(timezone.utc)  # Aware datetime
```

### Phase 5: Documentation (Optional, 1 day)

Add missing docstrings to public methods:

```python
# Before
class UserService:
    def get_user(self, user_id: str):
        return self.db.query(user_id)

# After
class UserService:
    def get_user(self, user_id: str) -> User:
        """
        Retrieve a user by ID.
        
        Args:
            user_id: The unique user identifier
            
        Returns:
            User object
            
        Raises:
            NotFoundError: If user doesn't exist
        """
        return self.db.query(user_id)
```

---

## 📋 Testing Requirements

### Regression Tests:
```python
# tests/test_linting_fixes.py

def test_type_annotations_still_work():
    """Test that updated type annotations are correct."""
    from src.module import process_items
    
    # Should accept modern type hints
    result: list[str] = process_items(["a", "b"])
    assert isinstance(result, list)
```

### Integration Tests:
```python
def test_application_builds():
    """Test that application builds after linting fixes."""
    import subprocess
    
    result = subprocess.run(
        ["ruff", "check", "src/", "--no-fix"],
        capture_output=True,
        text=True
    )
    
    # Should have zero errors (warnings OK for now)
    assert "error" not in result.stderr.lower()
```

---

## 📊 Progress Tracking

### Violation Reduction Target:

| Week | Target | Focus Area |
|------|--------|------------|
| 1 | 2,500 → 1,500 | Auto-fixable |
| 2 | 1,500 → 500 | Type annotations |
| 3 | 500 → 100 | Manual fixes |
| 4 | 100 → 0 | Final cleanup |

### Rule-by-Rule Progress:

| Rule | Initial | Target | Current | Status |
|------|---------|--------|---------|--------|
| COM812 | 847 | 0 | - | ⏳ |
| W293 | 521 | 0 | - | ⏳ |
| UP006 | 478 | 0 | - | ⏳ |
| UP045 | 386 | 0 | - | ⏳ |
| B904 | 157 | 0 | - | ⏳ |
| All others | ~600 | 0 | - | ⏳ |

---

## 📚 References

- **QA/QC Review:** Deep QA/QC Review - March 2026, Section 2.2
- **Ruff Documentation:** https://docs.astral.sh/ruff/
- **PEP 585:** [Type Hinting Generics in Standard Collections](https://peps.python.org/pep-0585/)
- **PEP 604:** [Allow Writing Union Types as X | Y](https://peps.python.org/pep-0604/)
- **Related Issues:** QAQC-004, QAQC-006

---

## 🎯 Success Metrics

- [ ] Zero ruff errors (F821, etc.)
- [ ] <100 ruff warnings
- [ ] 100% auto-fixable violations fixed
- [ ] Pre-commit hooks passing
- [ ] CI/CD validation green
- [ ] Developer satisfaction improved

---

## 📝 Additional Notes

### Pre-commit Hook Update:

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.1.14
  hooks:
    - id: ruff
      args: [--fix, --exit-non-zero-on-fix]
    - id: ruff-format
```

### CI/CD Validation:

```yaml
# .github/workflows/linting.yml
name: Linting

on: [push, pull_request]

jobs:
  ruff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install ruff
        run: pip install ruff
      
      - name: Run ruff check
        run: ruff check src/ --output-format=github
      
      - name: Run ruff format
        run: ruff format src/ --check
```

---

**Created from:** Deep QA/QC Review - March 3, 2026  
**Issue Template:** qaqc-code-quality.md
