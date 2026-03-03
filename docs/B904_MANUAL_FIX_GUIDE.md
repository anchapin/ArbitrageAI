# B904 Manual Fix Guide

## Overview

After running `python scripts/fix_b904.py`, some violations require manual review.
This guide helps you fix them systematically.

## What is B904?

**B904 (raise-without-from-inside-except)**: Within an `except` clause, raise exceptions 
with `raise ... from err` or `raise ... from None` to distinguish them from errors in 
exception handling.

## Why It Matters

```python
# ❌ BAD: Loses original exception context
try:
    db.query()
except DatabaseError:
    raise APIError("Query failed")

# ✅ GOOD: Preserves original exception
try:
    db.query()
except DatabaseError as exc:
    raise APIError("Query failed") from exc
```

## Fix Patterns

### Pattern 1: Simple Single-Line Raises

**Before:**
```python
except ValueError as e:
    raise CustomError("Invalid value")
```

**After:**
```python
except ValueError as exc:
    raise CustomError("Invalid value") from exc
```

### Pattern 2: Multi-Line Raises

**Before:**
```python
except httpx.HTTPError as e:
    raise AuthenticationError(
        f"Authentication failed: {str(e)}"
    )
```

**After:**
```python
except httpx.HTTPError as exc:
    raise AuthenticationError(
        f"Authentication failed: {str(exc)}"
    ) from exc
```

**Key Points:**
- Rename `e` to `exc` for consistency
- Add `from exc` at the end (before closing paren)
- Update f-string references from `e` to `exc`

### Pattern 3: Exception Type Without Variable

**Before:**
```python
except ValueError:
    raise CustomError("Invalid value")
```

**After (Option A - Preserve Context):**
```python
except ValueError as exc:
    raise CustomError("Invalid value") from exc
```

**After (Option B - Intentional Suppression):**
```python
except ValueError:
    raise CustomError("Invalid value") from None
```

**When to use Option B:**
- When the original exception is not relevant
- When you want to hide implementation details
- When the exception is expected and handled

### Pattern 4: Using str(e) in Message

**Before:**
```python
except DatabaseError as e:
    raise APIError(f"Database error: {str(e)}")
```

**After:**
```python
except DatabaseError as exc:
    raise APIError(f"Database error: {str(exc)}") from exc
```

**Key Points:**
- Change `e` to `exc` in both the `as` clause and the f-string
- Add `from exc` at the end

### Pattern 5: HTTPException in FastAPI

**Before:**
```python
except NotFoundError as e:
    raise HTTPException(
        status_code=404,
        detail=f"Resource not found: {e}"
    )
```

**After:**
```python
except NotFoundError as exc:
    raise HTTPException(
        status_code=404,
        detail=f"Resource not found: {exc}"
    ) from exc
```

## Step-by-Step Manual Fix Process

### Step 1: Identify the Violation

Ruff will show you the file and line number:
```
src/api/main.py:123:13: B904 Within an `except` clause, raise exceptions with...
```

### Step 2: Examine the Context

Look at the except clause and the raise statement:
```python
try:
    # some code
except SomeError as e:  # ← What exception variable?
    raise OtherError("msg")  # ← This needs 'from'
```

### Step 3: Apply the Fix

**If exception variable exists:**
```python
except SomeError as exc:
    raise OtherError("msg") from exc
```

**If no exception variable:**
```python
# Option A: Add variable and preserve context
except SomeError as exc:
    raise OtherError("msg") from exc

# Option B: Suppress context intentionally
except SomeError:
    raise OtherError("msg") from None
```

### Step 4: Update References

If the exception variable is used in the error message:
```python
# Before
except ValueError as e:
    raise CustomError(f"Invalid: {e}")

# After
except ValueError as exc:
    raise CustomError(f"Invalid: {exc}") from exc
```

### Step 5: Verify

Run ruff to confirm the fix:
```bash
ruff check src/api/main.py --select B904
```

## Common Scenarios

### Scenario 1: Multi-Line with Multiple Parameters

**Before:**
```python
except ValidationError as e:
    raise APIException(
        status_code=400,
        detail=str(e),
        code="VALIDATION_ERROR"
    )
```

**After:**
```python
except ValidationError as exc:
    raise APIException(
        status_code=400,
        detail=str(exc),
        code="VALIDATION_ERROR"
    ) from exc
```

### Scenario 2: Nested Exceptions

**Before:**
```python
try:
    try:
        risky_operation()
    except InnerError as e:
        raise OuterError("Inner failed")
except OuterError:
    raise FinalError("Operation failed")
```

**After:**
```python
try:
    try:
        risky_operation()
    except InnerError as exc:
        raise OuterError("Inner failed") from exc
except OuterError as exc:
    raise FinalError("Operation failed") from exc
```

### Scenario 3: Multiple Exception Types

**Before:**
```python
except (ValueError, TypeError) as e:
    raise CustomError("Invalid type or value")
```

**After:**
```python
except (ValueError, TypeError) as exc:
    raise CustomError("Invalid type or value") from exc
```

### Scenario 4: Re-raising with Additional Context

**Before:**
```python
except DatabaseError as e:
    logger.error(f"Database error: {e}")
    raise DatabaseError(f"Query failed: {e}")
```

**After:**
```python
except DatabaseError as exc:
    logger.error(f"Database error: {exc}")
    raise DatabaseError(f"Query failed: {exc}") from exc
```

## Special Cases

### Case 1: Intentional Context Suppression

Sometimes you want to hide the original exception:

```python
# Security: Don't expose internal details
except AuthenticationError:
    raise InvalidCredentialsError(
        "Invalid username or password"
    ) from None
```

**Use `from None` when:**
- Hiding implementation details for security
- Converting technical errors to user-friendly messages
- The original exception is not relevant to the caller

### Case 2: Bare Except Clauses

```python
# Before
except:
    raise CustomError("Something went wrong")

# After (Option A)
except Exception as exc:
    raise CustomError("Something went wrong") from exc

# After (Option B - if truly catching everything)
except Exception:
    raise CustomError("Something went wrong") from None
```

**Best Practice:** Avoid bare `except:` - use `except Exception:` instead.

### Case 3: Exception in Finally or Else Blocks

B904 only applies to `except` blocks. Raises in `finally` or `else` don't need `from`.

```python
try:
    operation()
except Error as exc:
    handle_error(exc)
    raise  # This is fine - re-raising same exception
finally:
    cleanup()  # Raises here don't need 'from'
```

## Testing Your Fixes

After fixing, run:

```bash
# Check for remaining B904 violations
ruff check src/ --select B904

# Run tests to ensure no regressions
pytest tests/ -v

# Run full linting
ruff check src/
```

## Quick Reference

| Pattern | Fix |
|---------|-----|
| `raise Error("msg")` | `raise Error("msg") from exc` |
| `raise Error(f"{e}")` | `raise Error(f"{exc}") from exc` |
| Multi-line raise | Add `from exc` before closing `)` |
| No exception var | Add `as exc` or use `from None` |
| Bare `except:` | Change to `except Exception as exc:` |

## Files Requiring Manual Review

After running the auto-fixer, check these files manually:

1. **Marketplace Adapters** - Complex error handling
2. **API Endpoints** - HTTPException with multiple parameters  
3. **Database Operations** - Transaction error handling
4. **Authentication** - Security-sensitive error messages

## Tips

1. **Be consistent**: Use `exc` as the exception variable name
2. **Preserve context**: Default to `from exc` unless there's a reason not to
3. **Security first**: Use `from None` for authentication/validation errors
4. **Test thoroughly**: Exception handling changes can affect error flows
5. **Update tests**: Ensure tests expect the chained exceptions

## Examples from the Codebase

### Example 1: Fiverr Adapter

**Location:** `src/agent_execution/marketplace_adapters/fiverr_adapter.py`

**Before:**
```python
except httpx.HTTPStatusError as e:
    if e.response.status_code == 429:
        raise RateLimitError("Fiverr rate limit exceeded")
    raise MarketplaceError(f"Fiverr search failed: {str(e)}")
```

**After:**
```python
except httpx.HTTPStatusError as exc:
    if exc.response.status_code == 429:
        raise RateLimitError("Fiverr rate limit exceeded") from exc
    raise MarketplaceError(f"Fiverr search failed: {str(exc)}") from exc
```

### Example 2: API Main

**Location:** `src/api/main.py`

**Before:**
```python
except TaskNotFoundError as e:
    raise HTTPException(
        status_code=404,
        detail=f"Task not found: {task_id}"
    )
```

**After:**
```python
except TaskNotFoundError as exc:
    raise HTTPException(
        status_code=404,
        detail=f"Task not found: {task_id}"
    ) from exc
```

## Resources

- [Ruff B904 Documentation](https://docs.astral.sh/ruff/rules/raise-without-from-inside-except/)
- [Python Exception Chaining](https://docs.python.org/3/tutorial/errors.html#exception-chaining)
- [PEP 3134 - Exception Chaining](https://peps.python.org/pep-3134/)
