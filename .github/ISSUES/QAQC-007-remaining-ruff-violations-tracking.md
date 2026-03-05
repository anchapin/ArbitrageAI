---
created: 2026-03-03
updated: 2026-03-03
priority: MEDIUM
qaqc_section: 2.2
estimated_effort: 40-60 hours
target_milestone: Phase 2 - Ongoing Code Quality
related_issue: "#209"
---

# [CODE QUALITY] Track Remaining Ruff Violations (439 Total)

## 📊 Issue Summary

**Priority:** MEDIUM  
**Labels:** code-quality, qaqc-review, ruff, tech-debt, tracking  
**Status:** Tracking Issue  
**Related:** #209 (Parent issue for ruff violations)

---

## 🎯 Overview

This is a **tracking issue** for the remaining 439 ruff linting violations in the ArbitrageAI codebase. 

As of March 3, 2026:
- **Starting violations:** 666 (Deep QA/QC Review)
- **Fixed in PR #210:** 227 violations (34% reduction)
- **Remaining violations:** 439

These violations require manual refactoring and will be addressed in follow-up PRs as part of continuous code quality improvements.

---

## 📈 Current Status

### Violations Breakdown by Type

| Rank | Violation Code | Count | Category | Effort | Priority |
|------|----------------|-------|----------|--------|----------|
| 1 | PLR6301 | 143 | no-self-use | High | Medium |
| 2 | D102 | 62 | undocumented-public-method | Medium | Medium |
| 3 | ARG002 | 34 | unused-method-argument | Low | Low |
| 4 | D107 | 23 | undocumented-public-init | Low | Medium |
| 5 | PERF203 | 23 | try-except-in-loop | Low | Low |
| 6 | RUF029 | 22 | unused-async | Medium | Medium |
| 7 | ARG001 | 20 | unused-function-argument | Low | Low |
| 8 | PLR1702 | 13 | too-many-nested-blocks | High | Medium |
| 9 | D205 | 11 | missing-blank-line-after-summary | Low | Low |
| 10 | N806 | 10 | non-lowercase-variable-in-function | Low | Low |
| 11 | PLR0917 | 9 | too-many-positional-arguments | Medium | Low |
| 12 | SIM102 | 9 | collapsible-if | Low | Low |
| 13 | ASYNC230 | 6 | blocking-open-call-in-async-function | Medium | Medium |
| 14 | D200 | 6 | unnecessary-multiline-docstring | Low | Low |
| 15 | PLW0603 | 4 | global-statement | Low | Low |
| 16 | PLW1508 | 4 | invalid-envvar-default | Low | Medium |
| 17 | RUF002 | 4 | ambiguous-unicode-character-docstring | Low | Low |
| 18 | RUF003 | 4 | ambiguous-unicode-character-comment | Low | Low |
| 19 | PLC2801 | 3 | unnecessary-dunder-call | Low | Low |
| 20 | PLR0911 | 3 | too-many-return-statements | Medium | Low |
| 21 | RUF012 | 3 | mutable-class-default | Medium | Medium |
| 22 | RUF022 | 3 | unsorted-dunder-all | Low | Low |
| 23 | D103 | 2 | undocumented-public-function | Low | Low |
| 24 | ERA001 | 2 | commented-out-code | Low | Low |
| 25 | PLR0904 | 2 | too-many-public-methods | High | Low |
| 26 | PLW0602 | 2 | global-variable-not-assigned | Low | Low |
| 27 | RUF001 | 2 | ambiguous-unicode-character-string | Low | Low |
| 28 | ASYNC110 | 1 | async-busy-wait | Medium | Medium |
| 29 | B027 | 1 | empty-method-without-abstract-decorator | Low | Low |
| 30 | E116 | 1 | unexpected-indentation-comment | Low | Low |
| 31 | N815 | 1 | mixed-case-variable-in-class-scope | Low | Low |
| 32 | PLR0914 | 1 | too-many-locals | Medium | Low |
| 33 | PLR6201 | 1 | literal-membership | Low | Low |
| 34 | PTH208 | 1 | os-listdir | Low | Low |
| 35 | RUF006 | 1 | asyncio-dangling-task | Medium | Medium |
| 36 | RUF045 | 1 | implicit-class-var-in-dataclass | Low | Low |
| 37 | SIM117 | 1 | multiple-with-statements | Low | Low |
| **Total** | **439** | | | | |

---

## 📁 Files with Most Violations

### Top 20 Files by Violation Count

| File | PLR6301 | D102/D107 | ARG | Other | Total | Priority |
|------|---------|-----------|-----|-------|-------|----------|
| `src/api/analytics.py` | 11 | - | 2 | - | 13 | Medium |
| `src/api/task_models.py` | - | 26 | - | - | 26 | Medium |
| `src/analytics/engines.py` | 8 | 1 | - | - | 9 | Medium |
| `src/utils/health_check.py` | 7 | 1 | - | - | 8 | Low |
| `src/fine_tuning/dataset_builder.py` | 7 | - | - | - | 7 | Medium |
| `src/api/financial_models.py` | - | 8 | - | - | 8 | Low |
| `src/disaster_recovery/recovery_manager.py` | 6 | - | 6 | - | 12 | Medium |
| `src/disaster_recovery/backup_manager.py` | 6 | - | 2 | - | 8 | Medium |
| `src/api/files.py` | - | 7 | - | - | 7 | Low |
| `src/disaster_recovery.py` | 5 | - | 4 | - | 9 | Medium |
| `src/agent_execution/planning.py` | 5 | - | 2 | - | 7 | Medium |
| `src/agent_execution/cost_tracker.py` | 5 | - | - | - | 5 | Low |
| `src/api/models_composition.py` | - | 6 | - | - | 6 | Low |
| `src/api/user_models.py` | - | 5 | - | - | 5 | Low |
| `src/utils/logging_alerting.py` | 4 | 3 | - | - | 7 | Low |
| `src/fine_tuning/cli.py` | 4 | - | - | - | 4 | Low |
| `src/agent_execution/intelligent_router.py` | 4 | - | - | - | 4 | Medium |
| `src/api/marketplace_models.py` | - | 4 | - | - | 4 | Low |
| `src/api/state_machine.py` | - | 3 | - | - | 3 | Low |
| `src/agent_execution/arena.py` | 2 | - | - | - | 2 | Low |

---

## 🔧 Recommended Fix Strategy

### Phase 1: Quick Wins (8-12 hours) - **Priority: HIGH**

These violations are easy to fix and provide immediate value:

#### 1.1 Docstrings (D102, D107, D205, D200) - 96 violations
**Effort:** Low-Medium  
**Impact:** Improved documentation

**Action Plan:**
- Add Google-style docstrings to public methods and `__init__`
- Fix blank lines in docstrings (D205)
- Format single-line docstrings (D200)

**Files to focus on:**
- `src/api/task_models.py` - 26 violations
- `src/api/financial_models.py` - 8 violations
- `src/api/files.py` - 7 violations

**Example Fix:**
```python
# Before
class TaskConfig:
    def __init__(self, name: str, model: str):
        self.name = name
        self.model = model

# After
class TaskConfig:
    """Task configuration container."""

    def __init__(self, name: str, model: str):
        """
        Initialize task configuration.

        Args:
            name: Task identifier
            model: Model name to use
        """
        self.name = name
        self.model = model
```

#### 1.2 Unused Arguments (ARG001, ARG002) - 54 violations
**Effort:** Low  
**Impact:** Cleaner code

**Action Plan:**
- Remove truly unused parameters
- Add `# noqa: ARG001` for interface compatibility
- Prefix unused params with underscore: `_kwargs`

**Files to focus on:**
- `src/api/disaster_recovery.py` - 11 violations
- `src/disaster_recovery/recovery_manager.py` - 6 violations

#### 1.3 Trivial Fixes (SIM102, D200, RUF002, RUF003, etc.) - 30 violations
**Effort:** Very Low  
**Impact:** Code cleanliness

**Action Plan:**
- Run `ruff check src/ --fix` for auto-fixable
- Manually fix remaining trivial issues

---

### Phase 2: Medium Effort (15-20 hours) - **Priority: MEDIUM**

#### 2.1 No-Self-Use (PLR6301) - 143 violations
**Effort:** Medium-High  
**Impact:** Better code organization

**Action Plan:**
1. **Convert to `@staticmethod`** (≈80 violations)
   - Utility methods that don't use instance state
   - Helper functions in classes

2. **Convert to `@classmethod`** (≈20 violations)
   - Factory methods
   - Methods using class-level constants

3. **Suppress with explanation** (≈43 violations)
   - Methods that may need instance state in future
   - Base class interface methods
   - Methods using only `self.logger`

**Files to focus on:**
- `src/api/analytics.py` - 11 violations
- `src/analytics/engines.py` - 8 violations
- `src/utils/health_check.py` - 7 violations
- `src/fine_tuning/dataset_builder.py` - 7 violations

**Example Fix:**
```python
# Before
class ProfitCalculator:
    def _calculate_variance(self, values: list[float]) -> float:
        # Doesn't use self
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)

# After
class ProfitCalculator:
    @staticmethod
    def _calculate_variance(values: list[float]) -> float:
        """Calculate variance of values."""
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)
```

#### 2.2 Unused Async (RUF029) - 22 violations
**Effort:** Medium  
**Impact:** Code clarity, minor performance

**Action Plan:**
- Remove `async` from synchronous functions
- Keep `async` with suppression if planning async DB migration
- Update call sites accordingly

**Files to focus on:**
- Review each case individually
- Check if async is intentional for future-proofing

#### 2.3 Too Many Nested Blocks (PLR1702) - 13 violations
**Effort:** Medium  
**Impact:** Improved readability

**Action Plan:**
- Extract nested logic into separate methods
- Use early returns to reduce nesting
- Use guard clauses

---

### Phase 3: Low Priority / Intentional (10-15 hours) - **Priority: LOW**

#### 3.1 Try-Except in Loop (PERF203) - 23 violations
**Effort:** Low (just add suppression)  
**Impact:** None (intentional pattern)

**Action Plan:**
- Add `# noqa: PERF203` with explanation
- These are intentional retry patterns

**Example:**
```python
for attempt in range(max_retries):
    try:
        result = await operation()
        return result
    except Exception as e:  # noqa: PERF203 - Retry pattern requires try-except in loop
        logger.warning(f"Attempt {attempt + 1} failed: {e}")
```

#### 3.2 Global Statement (PLW0603, PLW0602) - 6 violations
**Effort:** Low (add suppression)  
**Impact:** None (intentional singleton pattern)

**Action Plan:**
- Already suppressed in `pyproject.toml` for most files
- Add inline suppression for remaining cases

#### 3.3 Other Minor Violations - 30 violations
**Effort:** Low  
**Impact:** Code cleanliness

**Categories:**
- N806 (non-lowercase-variable): 10
- PLR0917 (too-many-positional-arguments): 9
- PLW1508 (invalid-envvar-default): 4
- RUF012 (mutable-class-default): 3
- ASYNC230 (blocking-open-call): 6
- Others: 10

---

## 📋 Sub-Issues to Create

Consider breaking this down into focused sub-issues:

1. **Issue #211:** [CODE QUALITY] Add Docstrings to Public Methods (D102, D107)
   - Focus: 85 docstring violations
   - Effort: 8-12 hours
   - Priority: Medium

2. **Issue #212:** [CODE QUALITY] Convert Methods to Static/Class Methods (PLR6301)
   - Focus: 143 no-self-use violations
   - Effort: 15-20 hours
   - Priority: Medium

3. **Issue #213:** [CODE QUALITY] Remove Unused Arguments (ARG001, ARG002)
   - Focus: 54 unused argument violations
   - Effort: 4-6 hours
   - Priority: Low

4. **Issue #214:** [CODE QUALITY] Remove Unused Async (RUF029)
   - Focus: 22 unused async violations
   - Effort: 4-6 hours
   - Priority: Medium

5. **Issue #215:** [CODE QUALITY] Fix Code Style Issues (SIM, N, RUF, etc.)
   - Focus: 50+ minor style violations
   - Effort: 4-6 hours
   - Priority: Low

---

## 📊 Progress Tracking

### Overall Progress
```
Starting:  ████████████████████ 666 violations
PR #210:   ████████████░░░░░░░░ 439 violations (34% reduction)
Phase 1:   ████████░░░░░░░░░░░░ ~350 violations (target)
Phase 2:   ████░░░░░░░░░░░░░░░░ ~200 violations (target)
Phase 3:   ██░░░░░░░░░░░░░░░░░░ ~100 violations (target)
Goal:      ░░░░░░░░░░░░░░░░░░░░ <50 violations (target)
```

### Burndown Chart (to be updated)

| Date | Total | PLR6301 | D102/D107 | ARG | Other | Notes |
|------|-------|---------|-----------|-----|-------|-------|
| 2026-03-03 | 439 | 143 | 85 | 54 | 157 | Baseline after PR #210 |
| | | | | | | |

---

## 🛠️ Tools & Commands

### Check Current Status
```bash
# Overall statistics
ruff check src/ --statistics

# Check specific violation type
ruff check src/ --select PLR6301
ruff check src/ --select D102,D107
ruff check src/ --select ARG

# Count by file
ruff check src/ --select PLR6301 | grep "\.py:" | cut -d: -f1 | sort | uniq -c | sort -rn

# Auto-fix what's possible
ruff check src/ --fix
```

### Track Progress
```bash
# Save violations to JSON for analysis
ruff check src/ --output-format=json > ruff_violations.json

# Create progress report
ruff check src/ --statistics > ruff_progress.txt
```

---

## 📚 References

- **Parent Issue:** #209 - Remaining Ruff Violations
- **PR #210:** Fixed 227 violations (34% reduction)
- **Ruff Documentation:** https://docs.astral.sh/ruff/
- **QA/QC Review:** Deep QA/QC Review - March 2026, Section 2.2

---

## ✅ Success Criteria

### Short-term (1-2 weeks)
- [ ] Phase 1 complete: Docstrings added (96 violations fixed)
- [ ] Phase 1 complete: Unused arguments removed (54 violations fixed)
- [ ] Total reduction: 439 → ~290 violations

### Medium-term (3-4 weeks)
- [ ] Phase 2 complete: Methods converted to static/class (143 violations fixed)
- [ ] Phase 2 complete: Unused async removed (22 violations fixed)
- [ ] Total reduction: 439 → ~130 violations

### Long-term (6-8 weeks)
- [ ] Phase 3 complete: Minor violations fixed (50+ violations fixed)
- [ ] Total reduction: 439 → <50 violations
- [ ] Code quality grade: A
- [ ] All critical paths documented

---

## 📝 Notes

### Intentional Patterns
Some violations are intentional and should be suppressed rather than fixed:
- **PERF203:** Retry patterns require try-except in loops
- **PLW0603/PLW0602:** Singleton patterns use global statement
- **ARG001/ARG002:** Interface compatibility requires unused parameters
- **PLC0415:** Lazy imports avoid circular dependencies (already suppressed)

### Configuration Updates
Add to `pyproject.toml` as needed:
```toml
[tool.ruff.lint.per-file-ignores]
# Add new suppressions for intentional patterns
"src/path/to/file.py" = ["PLR6301", "ARG001"]
```

### Testing
After fixing violations:
```bash
# Run tests to ensure no regression
python -m pytest tests/ -x --timeout=30

# Verify ruff check passes
ruff check src/
```

---

**Created from:** Ruff Violations Tracking - March 3, 2026  
**Related PR:** #210  
**Issue Template:** qaqc-code-quality.md
