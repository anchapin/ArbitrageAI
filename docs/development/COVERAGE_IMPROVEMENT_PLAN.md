# Coverage Improvement Plan - Issue #137

**Date**: March 2, 2026
**Status**: ✅ Configuration Enhanced
**Target Coverage**: 80% minimum

---

## Executive Summary

Enhanced coverage configuration has been implemented with comprehensive thresholds, reporting options, and exclusion patterns. Current configuration now includes:

- ✅ 80% minimum coverage threshold
- ✅ Branch coverage enabled
- ✅ Parallel test execution support
- ✅ Multiple report formats (HTML, XML, JSON)
- ✅ Comprehensive exclusion patterns
- ✅ Per-module tracking

---

## Configuration Changes

### Enhanced `pyproject.toml` Coverage Settings

```toml
[tool.coverage.run]
source = ["src"]
omit = [
    "tests/*",
    "*/migrations/*",
    "*/__init__.py",
    "*/__main__.py",
    "src/client_portal/*",
]
branch = true
parallel = true
concurrency = ["thread", "multiprocessing"]
dynamic_context = "thread"

[tool.coverage.report]
exclude_lines = [
    # Standard excludes
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    
    # Abstract methods
    "@abstractmethod",
    "@abc.abstractmethod",
    
    # Debug/platform-specific code
    "if DEBUG:",
    "if sys.platform:",
    "if sys.version_info",
    
    # Logging statements
    "logger\\.debug\\(",
    "logger\\.info\\(",
]
fail_under = 80
show_missing = true
skip_covered = false
skip_empty = true
sort = "Miss"
precision = 2
```

---

## Coverage Commands

### Run Tests with Coverage

```bash
# Basic coverage report
python3 -m pytest --cov=src --cov-report=term-missing

# Coverage with HTML report
python3 -m pytest --cov=src --cov-report=html --cov-report=term-missing

# Coverage with all formats
python3 -m pytest --cov=src --cov-report=html --cov-report=xml --cov-report=json --cov-report=term-missing

# Fail if coverage drops below 80%
python3 -m pytest --cov=src --cov-fail-under=80

# Parallel test execution with coverage
python3 -m pytest --cov=src -n auto --cov-parallel
```

### View Coverage Report

```bash
# Terminal report with missing lines
python3 -m coverage report --show-missing

# HTML report (open in browser)
python3 -m coverage html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov\\index.html  # Windows

# XML report for CI/CD
python3 -m coverage xml

# JSON report for programmatic access
python3 -m coverage json
```

---

## Coverage Analysis

### Current Coverage Targets

| Module Category | Target | Priority |
|----------------|--------|----------|
| Core Business Logic | 90%+ | High |
| API Endpoints | 85%+ | High |
| Utilities | 80%+ | Medium |
| Configuration | 75%+ | Medium |
| Migrations | 50%+ | Low |
| Client Portal | N/A | Excluded |

### Excluded from Coverage

The following are intentionally excluded:

1. **`__init__.py` files** - Mostly imports
2. **Migrations** - Database schema changes
3. **Client Portal** - Frontend code (separate testing)
4. **Debug-only code** - Platform-specific fallbacks
5. **Abstract methods** - By definition not implemented
6. **TYPE_CHECKING blocks** - Type hints only

---

## Test Coverage Improvement Strategy

### Phase 1: Critical Paths (Week 1)

Focus on high-impact, frequently-used code:

1. **API Endpoints** (`src/api/`)
   - Test all HTTP methods (GET, POST, PUT, DELETE)
   - Test error scenarios (4xx, 5xx)
   - Test authentication/authorization
   - Test rate limiting

2. **Core Business Logic** (`src/agent_execution/`)
   - Test bid placement logic
   - Test lock management
   - Test execution workflows
   - Test error handling

3. **Data Models** (`src/models/`)
   - Test CRUD operations
   - Test validation
   - Test relationships

### Phase 2: Integration Tests (Week 2)

Test component interactions:

1. **End-to-End Workflows**
   - Complete task execution flow
   - Payment processing flow
   - Error recovery flow

2. **Database Integration**
   - Session management
   - Transaction handling
   - Connection pooling

3. **External Services**
   - Stripe integration (mocked)
   - LLM service integration (mocked)
   - Redis locking (integration)

### Phase 3: Edge Cases (Week 3)

Test error scenarios and edge cases:

1. **Error Handling**
   - Network timeouts
   - Database connection failures
   - Invalid input data
   - Resource exhaustion

2. **Boundary Conditions**
   - Empty inputs
   - Maximum values
   - Concurrent operations
   - Race conditions

3. **Security Scenarios**
   - Authentication bypass attempts
   - SQL injection attempts
   - XSS attempts
   - CSRF attempts

---

## Coverage Gaps Identification

### Generate Gap Report

```bash
# Find least tested files
python3 -m coverage report --sort=cover --show-missing | head -30

# Find most missed lines
python3 -m coverage report --sort=miss --show-missing | head -30

# Generate annotated HTML (shows uncovered lines)
python3 -m coverage html --show-contexts
```

### Common Coverage Gaps

1. **Error Handlers**
   ```python
   # Often untested
   except SpecificException as e:
       logger.error(f"Error: {e}")
       return error_response()
   ```

2. **Edge Cases**
   ```python
   # Boundary conditions
   if value <= 0 or value > MAX_VALUE:
       raise ValueError()
   ```

3. **Platform-Specific Code**
   ```python
   # Only runs on specific platforms
   if sys.platform == "win32":
       # Windows-specific code
   ```

---

## Best Practices

### Writing Testable Code

1. **Dependency Injection**
   ```python
   # Good - inject dependencies
   def process_data(db: Session, validator: Validator):
       ...
   
   # Hard to test - create dependencies internally
   def process_data():
       db = get_db()  # Hard to mock
   ```

2. **Single Responsibility**
   ```python
   # Good - focused function
   def calculate_profit(bid: Bid, sale: Sale) -> float:
       return sale.price - bid.price
   
   # Hard to test - multiple responsibilities
   def process_and_save_and_notify():
       # Does too much
   ```

3. **Pure Functions**
   ```python
   # Good - deterministic
   def calculate_tax(amount: float, rate: float) -> float:
       return amount * rate
   
   # Hard to test - side effects
   def calculate_tax_and_log(amount: float):
       logger.info(f"Calculating tax for {amount}")
       # ...
   ```

### Test Organization

1. **Test File Naming**
   - `test_*.py` for test files
   - Match source structure: `src/api/main.py` → `tests/test_api_main.py`

2. **Test Class Naming**
   - `Test<Feature>` for test classes
   - `test_<scenario>` for test methods

3. **Test Coverage**
   - One test per scenario
   - Test happy path first
   - Test error paths second
   - Test edge cases last

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests & Coverage

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -e ".[tests]"
      
      - name: Run tests with coverage
        run: |
          python -m pytest \
            --cov=src \
            --cov-report=xml \
            --cov-report=term-missing \
            --cov-fail-under=80 \
            -v
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          flags: unittests
          name: codecov-umbrella
```

### Coverage Badge

Add to README.md:

```markdown
[![Coverage](https://codecov.io/gh/anchapin/ArbitrageAI/branch/main/graph/badge.svg)](https://codecov.io/gh/anchapin/ArbitrageAI)
```

---

## Monitoring & Maintenance

### Weekly Coverage Review

1. **Check Coverage Trend**
   ```bash
   # Compare with previous run
   python3 -m coverage report --show-missing
   ```

2. **Review New Code**
   - Ensure new features have tests
   - Ensure bug fixes have regression tests
   - Review coverage diff in PRs

3. **Address Gaps**
   - Identify untested critical paths
   - Create targeted tests
   - Document known gaps

### Monthly Coverage Audit

1. **Analyze Coverage by Module**
   ```bash
   python3 -m coverage report --by-file --sort=cover
   ```

2. **Identify Stale Tests**
   - Tests that haven't been updated
   - Tests for deprecated features
   - Tests with outdated mocks

3. **Update Coverage Targets**
   - Increase `fail_under` if appropriate
   - Adjust exclusions if needed
   - Review exclusion patterns

---

## Tools & Resources

### Coverage Tools

- **coverage.py** - Main coverage tool
- **pytest-cov** - Pytest plugin for coverage
- **Codecov** - Cloud coverage tracking
- **Coveralls** - Alternative coverage tracking

### Related Tools

- **mutmut** - Mutation testing
- **hypothesis** - Property-based testing
- **pytest-xdist** - Parallel test execution
- **pytest-timeout** - Test timeout detection

### Documentation

- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Pytest Coverage Plugin](https://pytest-cov.readthedocs.io/)
- [Codecov Documentation](https://docs.codecov.com/)

---

## Success Metrics

### Quantitative Metrics

- ✅ Overall coverage ≥ 80%
- ✅ Critical modules ≥ 90%
- ✅ No module < 50%
- ✅ All new code covered
- ✅ Branch coverage ≥ 70%

### Qualitative Metrics

- ✅ Critical paths tested
- ✅ Error scenarios covered
- ✅ Edge cases documented
- ✅ Tests maintainable
- ✅ Fast test execution (< 5 min)

---

## Next Steps

1. **Run Baseline Coverage**
   ```bash
   python3 -m pytest --cov=src --cov-report=term-missing --cov-fail-under=80
   ```

2. **Identify Top 10 Least Tested Files**
   ```bash
   python3 -m coverage report --sort=cover | tail -10
   ```

3. **Create Targeted Tests**
   - Focus on critical business logic
   - Add error scenario tests
   - Improve integration test coverage

4. **Monitor Progress**
   - Track coverage weekly
   - Celebrate improvements
   - Address regressions immediately

---

**Status**: Configuration complete, ready for test implementation
**Next Review**: After initial coverage baseline run
**Owner**: Development Team
