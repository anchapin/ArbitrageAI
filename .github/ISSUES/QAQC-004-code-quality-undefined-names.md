---
created: 2026-03-03
priority: HIGH
qaqc_section: 2.2
estimated_effort: 5 days
target_milestone: Phase 2 - Week 3-4
---

# [CODE QUALITY] Fix 50 Undefined Name Errors (F821)

## 🐛 Code Quality Issue - Potential Bugs

**Priority:** HIGH  
**Labels:** code-quality, bugs, qaqc-review, ruff  
**QA/QC Review Reference:** Section 2.2 - Ruff Linting Violations

---

## 📍 Location

- **Files:** Multiple files across codebase (to be identified)
- **Ruff Rule:** F821 (undefined-name)
- **Count:** 50 occurrences
- **Component:** Various

---

## 🐛 Issue Description

Ruff has identified **50 undefined name errors** (F821) in the codebase. These represent potential bugs where:

1. Variables are used before being defined
2. Functions reference non-existent variables
3. Typos in variable names
4. Missing imports
5. Incorrect attribute access

Example pattern:
```python
def process_data():
    result = data  # F821: 'data' is not defined
    return result
```

---

## ⚠️ Risk Assessment

- **Severity:** High (potential runtime errors)
- **Impact:** Application crashes, unexpected behavior
- **Likelihood:** Medium (depends on code paths executed)
- **Technical Debt:** Accumulating over time

---

## 🎯 Acceptance Criteria

- [ ] All 50 F821 errors identified and fixed
- [ ] No new F821 errors introduced
- [ ] All tests passing after fixes
- [ ] Ruff check passes without F821 errors
- [ ] Code review completed
- [ ] No regression in functionality

---

## 🔧 Implementation Notes

### Step 1: Identify All F821 Errors

Run ruff to get detailed list:

```bash
ruff check src/ --select F821 --output-format=json > f821_errors.json
```

### Step 2: Categorize Errors

Common categories:

#### Category 1: Missing Imports
```python
# Before
def process():
    return json.dumps(data)  # F821: json not defined

# After
import json

def process():
    return json.dumps(data)
```

#### Category 2: Typos in Variable Names
```python
# Before
def calculate(user_data):
    return user_dat["count"]  # Typo: user_dat vs user_data

# After
def calculate(user_data):
    return user_data["count"]
```

#### Category 3: Undefined Variables
```python
# Before
def process():
    if condition:
        result = True
    return result  # F821: result might not be defined

# After
def process():
    result = False
    if condition:
        result = True
    return result
```

#### Category 4: Scope Issues
```python
# Before
def outer():
    if True:
        inner_var = 5
    print(inner_var)  # F821 in some contexts

# After
def outer():
    inner_var = None
    if True:
        inner_var = 5
    print(inner_var)
```

#### Category 5: Missing Self
```python
# Before
class MyClass:
    def method(self):
        return value  # F821: should be self.value

# After
class MyClass:
    def method(self):
        return self.value
```

### Step 3: Fix Systematically

Create a script to help:

```python
# scripts/fix_f821.py
import subprocess
import json

def get_f821_errors():
    """Get all F821 errors from ruff."""
    result = subprocess.run(
        ["ruff", "check", "src/", "--select", "F821", "--output-format", "json"],
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)

def categorize_errors(errors):
    """Categorize errors for easier fixing."""
    categories = {
        "missing_import": [],
        "typo": [],
        "undefined_variable": [],
        "scope_issue": [],
        "missing_self": [],
        "other": [],
    }
    
    for error in errors:
        # Analyze error and categorize
        # This would need manual review or AI assistance
        pass
    
    return categories

if __name__ == "__main__":
    errors = get_f821_errors()
    print(f"Found {len(errors)} F821 errors")
    categories = categorize_errors(errors)
    
    for category, errs in categories.items():
        print(f"\n{category}: {len(errs)} errors")
```

---

## 📋 Testing Requirements

### Regression Tests:
```python
# tests/test_f821_fixes.py

def test_all_previously_undefined_variables():
    """Test that all previously undefined variables now work."""
    # Add tests for each fixed F821 error
    # This ensures the fix didn't break functionality
    
    # Example:
    from src.module import function_with_previously_undefined_var
    
    result = function_with_previously_undefined_var()
    assert result is not None
```

### Integration Tests:
```python
def test_application_startup():
    """Test that application starts without NameError."""
    # This would have failed before fixing F821 errors
    from src.api.main import app
    
    assert app is not None
```

---

## 📊 Progress Tracking

Create a tracking spreadsheet:

| # | File | Line | Variable | Category | Status | Fixed By |
|---|------|------|----------|----------|--------|----------|
| 1 | src/api/main.py | 123 | `data` | Missing import | ✅ Fixed | Alex |
| 2 | src/executor.py | 456 | `user_id` | Typo | ✅ Fixed | Alex |
| ... | ... | ... | ... | ... | ... | ... |

---

## 📚 References

- **QA/QC Review:** Deep QA/QC Review - March 2026, Section 2.2
- **Ruff Rule:** [F821 - undefined-name](https://docs.astral.sh/ruff/rules/undefined-name/)
- **Python Documentation:** [NameError](https://docs.python.org/3/library/exceptions.html#NameError)
- **Related Issues:** QAQC-007 (Fix all ruff violations)

---

## 🎯 Success Metrics

- [ ] 50/50 F821 errors fixed
- [ ] Zero F821 errors in ruff check
- [ ] All tests passing
- [ ] No new NameError exceptions in production
- [ ] Code coverage maintained or improved

---

## 📝 Additional Notes

### Priority Order:
1. Fix errors in critical paths (payment, authentication)
2. Fix errors in frequently-used code
3. Fix errors in test code
4. Fix errors in utility functions

### Tools to Use:
- `ruff check src/ --select F821` - Find errors
- `ruff check src/ --select F821 --fix` - Auto-fix where possible
- IDE inspections - Help identify issues
- Git blame - Understand context

### Common Patterns to Watch For:
```python
# Pattern 1: Typo in variable name
for item in items:
    process(itm)  # Should be item

# Pattern 2: Missing import
def parse_json():
    return json.loads("{}")  # import json missing

# Pattern 3: Wrong attribute
class User:
    def __init__(self):
        self.name = "test"

user = User()
print(user.nme)  # Typo: nme vs name
```

---

**Created from:** Deep QA/QC Review - March 3, 2026  
**Issue Template:** qaqc-code-quality.md
