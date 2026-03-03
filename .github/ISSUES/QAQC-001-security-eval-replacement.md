---
created: 2026-03-03
priority: CRITICAL
qaqc_section: 1.1
estimated_effort: 2 days
target_milestone: Phase 1 - Week 1-2
---

# [SECURITY] Replace eval() with Safe Expression Parser in logging_alerting.py

## 🔴 Critical Security Vulnerability

**Priority:** CRITICAL  
**Labels:** security, critical, qaqc-review, tech-debt  
**QA/QC Review Reference:** Section 1.2 - Use of `eval()` in Production Code

---

## 📍 Location

- **File:** `src/utils/logging_alerting.py`
- **Line:** 460
- **Component:** Logging & Alerting System

---

## 🐛 Issue Description

The code currently uses Python's built-in `eval()` function to evaluate conditions:

```python
# Line 460
return eval(condition, {"__builtins__": {}}, metrics)
```

Even with restricted builtins (`{"__builtins__": {}}`), this is a potential code injection vector. An attacker who can influence the `condition` parameter could potentially:

1. Access sensitive data through closure variables
2. Exploit Python object model weaknesses
3. Bypass the restricted builtins using advanced techniques

---

## ⚠️ Risk Assessment

- **Severity:** Critical
- **Impact:** Remote Code Execution (RCE) potential
- **Likelihood:** Medium (depends on how `condition` is populated)
- **CVSS Score (estimated):** 8.1 (High)

---

## 🎯 Acceptance Criteria

- [ ] `eval()` completely removed from codebase
- [ ] Safe expression parser implemented (e.g., `ast.literal_eval()` or `simpleeval`)
- [ ] All existing tests passing
- [ ] New security tests added to prevent regression
- [ ] Security documentation updated
- [ ] Security review completed by team

---

## 🔧 Implementation Notes

### Recommended Solutions (in order of preference):

#### Option 1: Use `simpleeval` Library
```python
from simpleeval import simple_eval

# Safe evaluation with controlled operators
return simple_eval(condition, names=metrics)
```

**Pros:**
- Designed for safe expression evaluation
- Supports operators, functions, and names
- Actively maintained
- No builtins access

**Cons:**
- Adds new dependency

#### Option 2: Use `ast.literal_eval()` (Limited)
```python
import ast

# Only works for literal expressions (dicts, lists, strings, numbers)
return ast.literal_eval(condition)
```

**Pros:**
- Built-in, no dependencies
- Very safe

**Cons:**
- Only supports literals, no operators or logic

#### Option 3: Custom AST Parser
```python
import ast

class SafeEvalVisitor(ast.NodeVisitor):
    """AST visitor that only allows safe operations."""
    
    def visit_BinOp(self, node):
        # Only allow specific operations
        if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            # Process safely
            pass
        else:
            raise ValueError("Unsafe operation")
```

**Pros:**
- Full control over allowed operations
- No dependencies

**Cons:**
- More complex to implement correctly
- Requires thorough testing

---

## 📋 Testing Requirements

### Security Tests to Add:
```python
def test_eval_injection_attempts():
    """Test that malicious expressions are rejected."""
    malicious_inputs = [
        "__import__('os').system('rm -rf /')",
        "globals()['__builtins__']",
        "().__class__.__mro__[1].__subclasses__()",
        "eval('malicious')",
        "exec('code')",
    ]
    
    for malicious in malicious_inputs:
        with pytest.raises((ValueError, SyntaxError)):
            safe_evaluate(malicious, metrics={})
```

### Regression Tests:
```python
def test_safe_expression_evaluation():
    """Test that legitimate expressions still work."""
    test_cases = [
        ("cpu_usage > 80", {"cpu_usage": 90}, True),
        ("memory_mb < 1000", {"memory_mb": 500}, True),
        ("error_rate < 0.01", {"error_rate": 0.05}, False),
    ]
    
    for expr, metrics, expected in test_cases:
        result = safe_evaluate(expr, metrics)
        assert result == expected
```

---

## 📚 References

- **QA/QC Review:** Deep QA/QC Review - March 2026, Section 1.2
- **Python Documentation:** [eval() dangers](https://docs.python.org/3/library/functions.html#eval)
- **OWASP:** [Code Injection](https://owasp.org/www-community/attacks/Code_Injection)
- **simpleeval:** https://github.com/danthedeckie/simpleeval
- **Related Issues:** None yet

---

## 🎯 Success Metrics

- [ ] Zero `eval()` calls in production code
- [ ] All security tests passing
- [ ] No regression in alerting functionality
- [ ] Security audit passed

---

## 📝 Additional Notes

This is part of the Phase 1 Critical Security fixes from the QA/QC review. Complete this before moving to Phase 2.

**Related files to review:**
- `src/utils/logging_alerting.py` - Main file to fix
- `tests/test_logging_alerting.py` - Tests to update
- `SECURITY.md` - Update with safe evaluation guidelines

---

**Created from:** Deep QA/QC Review - March 3, 2026  
**Issue Template:** qaqc-critical-security.md
