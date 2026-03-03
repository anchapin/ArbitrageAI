---
created: 2026-03-03
priority: HIGH
qaqc_section: 2.2
estimated_effort: 3 days
target_milestone: Phase 2 - Week 3-4
---

# [CODE QUALITY] Fix Exception Handling Anti-Patterns (B904)

## 🐛 Code Quality Issue - Error Handling

**Priority:** HIGH  
**Labels:** code-quality, error-handling, qaqc-review, ruff  
**QA/QC Review Reference:** Section 2.2 - Ruff Linting Violations (B904)

---

## 📍 Location

- **Files:** Multiple files across codebase
- **Ruff Rule:** B904 (raise-without-from-inside-except)
- **Count:** 157 occurrences
- **Component:** Error handling throughout application

---

## 🐛 Issue Description

The codebase has **157 instances** of raising exceptions without preserving the original exception context:

```python
# Anti-pattern (157 occurrences)
try:
    risky_operation()
except SomeError:
    raise OtherError("operation failed")  # Loses original traceback!
```

This makes debugging extremely difficult because:
1. Original exception type is lost
2. Stack trace doesn't show root cause
3. Error messages lack context
4. Production debugging becomes guesswork

---

## ⚠️ Risk Assessment

- **Severity:** High (impacts debugging and incident response)
- **Impact:** Increased MTTR (Mean Time To Resolution)
- **Likelihood:** Certain (will affect next production incident)
- **Technical Debt:** Severe

---

## 🎯 Acceptance Criteria

- [ ] All 157 B904 violations fixed
- [ ] Exception context preserved with `from` keyword
- [ ] All tests passing
- [ ] Error messages improved with context
- [ ] Code review completed
- [ ] Error handling guidelines documented

---

## 🔧 Implementation Notes

### The Problem

**Before (loses context):**
```python
try:
    db.execute(query)
except SQLAlchemyError:
    raise DatabaseError("Failed to execute query")
# Original traceback is lost!
```

**After (preserves context):**
```python
try:
    db.execute(query)
except SQLAlchemyError as exc:
    raise DatabaseError("Failed to execute query") from exc
# Full traceback preserved!
```

### Fix Pattern 1: Explicit Context Preservation

```python
# Before
try:
    response = requests.get(url)
    response.raise_for_status()
except requests.RequestException:
    raise APIError("Request failed")

# After
try:
    response = requests.get(url)
    response.raise_for_status()
except requests.RequestException as exc:
    raise APIError(f"Request failed: {url}") from exc
```

### Fix Pattern 2: Add Context Information

```python
# Before
try:
    user = db.query(User).filter(User.id == user_id).one()
except NoResultFound:
    raise NotFoundError("User not found")

# After
try:
    user = db.query(User).filter(User.id == user_id).one()
except NoResultFound as exc:
    raise NotFoundError(f"User not found: id={user_id}") from exc
```

### Fix Pattern 3: When Original Context Isn't Needed

If you truly want to suppress the original exception (rare):

```python
try:
    value = config["critical_key"]
except KeyError:
    raise ConfigurationError("Missing critical configuration") from None
# Explicitly use "from None" to show intentional suppression
```

### Fix Pattern 4: Multiple Exception Types

```python
# Before
try:
    process_data()
except (ValueError, TypeError) as e:
    raise ProcessingError("Data processing failed")

# After
try:
    process_data()
except (ValueError, TypeError) as exc:
    raise ProcessingError(f"Data processing failed: {exc}") from exc
```

### Automated Fix Script

```python
# scripts/fix_b904.py
"""
Script to help identify and fix B904 violations.
Note: Manual review is still required.
"""

import re
from pathlib import Path

def find_b904_violations(directory: Path):
    """Find potential B904 violations in Python files."""
    pattern = re.compile(
        r'except\s+\w+.*:\s*\n\s*raise\s+\w+\(',
        re.MULTILINE
    )
    
    violations = []
    
    for py_file in directory.rglob("*.py"):
        if "test" in str(py_file):
            continue  # Skip test files
        
        content = py_file.read_text()
        matches = pattern.finditer(content)
        
        for match in matches:
            # Check if 'from' is present
            line_start = match.start()
            line_end = content.find('\n', line_start)
            line = content[line_start:line_end]
            
            if 'from' not in line and 'from None' not in line:
                violations.append({
                    'file': py_file,
                    'line': content[:line_start].count('\n') + 1,
                    'match': match.group()
                })
    
    return violations

if __name__ == "__main__":
    violations = find_b904_violations(Path("src"))
    print(f"Found {len(violations)} potential B904 violations:")
    
    for v in violations[:20]:  # Show first 20
        print(f"  {v['file']}:{v['line']}")
```

---

## 📋 Testing Requirements

### Unit Tests:
```python
# tests/test_error_handling.py

def test_exception_context_preserved():
    """Test that exception context is preserved."""
    from src.module import risky_operation
    
    try:
        risky_operation()
    except CustomError as exc:
        # Verify original exception is in __cause__
        assert exc.__cause__ is not None
        assert isinstance(exc.__cause__, OriginalError)
```

### Integration Tests:
```python
def test_error_messages_include_context():
    """Test that error messages include helpful context."""
    from src.module import process_user_data
    
    with pytest.raises(ProcessingError) as exc_info:
        process_user_data(invalid_data)
    
    # Error message should include context
    assert "user_id" in str(exc_info.value)
    assert exc_info.value.__cause__ is not None
```

---

## 📊 Progress Tracking

| Phase | Files | Count | Status |
|-------|-------|-------|--------|
| 1 | src/api/ | ~40 | ⏳ Pending |
| 2 | src/agent_execution/ | ~60 | ⏳ Pending |
| 3 | src/utils/ | ~30 | ⏳ Pending |
| 4 | src/fine_tuning/ | ~15 | ⏳ Pending |
| 5 | Other | ~12 | ⏳ Pending |

---

## 📚 References

- **QA/QC Review:** Deep QA/QC Review - March 2026, Section 2.2
- **Ruff Rule:** [B904 - raise-without-from-inside-except](https://docs.astral.sh/ruff/rules/raise-without-from-inside-except/)
- **Python Documentation:** [Exception Chaining](https://docs.python.org/3/tutorial/errors.html#exception-chaining)
- **PEP 3134:** [Exception Chaining and Embedded Tracebacks](https://peps.python.org/pep-3134/)
- **Related Issues:** QAQC-004, QAQC-007

---

## 🎯 Success Metrics

- [ ] 157/157 B904 violations fixed
- [ ] Zero B904 errors in ruff check
- [ ] All tests passing
- [ ] Error messages more helpful (team survey)
- [ ] MTTR reduced in production incidents

---

## 📝 Additional Notes

### Priority Order:
1. Fix in error handling paths (authentication, payment)
2. Fix in API endpoints
3. Fix in background tasks
4. Fix in utility functions

### Code Review Checklist:
- [ ] `from exc` added to all raises
- [ ] Error messages include context
- [ ] `from None` used only when intentional
- [ ] Original exception type documented if relevant

### Common Mistakes to Avoid:
```python
# ❌ Still loses context
raise OtherError from exc  # Missing message!

# ✅ Better
raise OtherError("descriptive message") from exc

# ❌ Wrong: creates new exception in except block
try:
    ...
except Error as exc:
    new_exc = OtherError("msg")
    raise new_exc  # No 'from'!

# ✅ Correct
try:
    ...
except Error as exc:
    raise OtherError("msg") from exc
```

---

**Created from:** Deep QA/QC Review - March 3, 2026  
**Issue Template:** qaqc-code-quality.md
