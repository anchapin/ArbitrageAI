#!/usr/bin/env python3
"""
Performance Improvements Verification Script

Issue #192: Redis-based Rate Limiting
Issue #193: N+1 Query Fixes with Eager Loading  
Issue #194: Database Indexes

This script verifies that all performance improvements are correctly implemented.

Usage:
    python scripts/verify_performance_improvements.py
"""

import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_check(name: str, passed: bool, details: str = ""):
    """Print a check result."""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  [{status}] {name}")
    if details:
        print(f"         {details}")


# =============================================================================
# ISSUE #192: REDIS RATE LIMITING VERIFICATION
# =============================================================================

def verify_redis_rate_limiter():
    """Verify Redis rate limiter implementation."""
    print_header("Issue #192: Redis-based Rate Limiting")

    checks_passed = 0
    total_checks = 0

    # Check 1: Module imports correctly
    total_checks += 1
    try:
        from api.rate_limiter import RedisRateLimiter, RateLimiter, QuotaManager
        print_check("RedisRateLimiter module imports", True)
        checks_passed += 1
    except ImportError as e:
        print_check("RedisRateLimiter module imports", False, str(e))

    # Check 2: Lua scripts are defined
    total_checks += 1
    try:
        from api.rate_limiter import RATE_LIMIT_LUA_SCRIPT, BURST_LIMIT_LUA_SCRIPT
        has_incr = "INCR" in RATE_LIMIT_LUA_SCRIPT
        has_expire = "EXPIRE" in RATE_LIMIT_LUA_SCRIPT
        passed = has_incr and has_expire
        print_check("Lua scripts define atomic INCR/EXPIRE", passed)
        if passed:
            checks_passed += 1
    except Exception as e:
        print_check("Lua scripts define atomic INCR/EXPIRE", False, str(e))

    # Check 3: RateLimiter maintains backward compatibility
    total_checks += 1
    try:
        from api.rate_limiter import RateLimiter
        from api.models import UserQuota, PricingTier

        limiter = RateLimiter()
        quota = UserQuota(
            user_id="test",
            tier=PricingTier.FREE,
            rate_limit_rps=10,
            rate_limit_burst=50,
        )

        # Test original API
        allowed, details = limiter.is_allowed("test_user", quota=quota)
        passed = allowed is True and "allowed" in details
        print_check("Backward compatible API (UserQuota)", passed)
        if passed:
            checks_passed += 1
    except Exception as e:
        print_check("Backward compatible API (UserQuota)", False, str(e))

    # Check 4: In-memory fallback exists
    total_checks += 1
    try:
        from api.rate_limiter import RedisRateLimiter
        limiter = RedisRateLimiter(redis_host="nonexistent", redis_port=9999)
        passed = limiter._redis is None and hasattr(limiter, "_check_memory")
        print_check("In-memory fallback when Redis unavailable", passed)
        if passed:
            checks_passed += 1
    except Exception as e:
        print_check("In-memory fallback when Redis unavailable", False, str(e))

    # Check 5: New API with explicit limits
    total_checks += 1
    try:
        from api.rate_limiter import RedisRateLimiter
        limiter = RedisRateLimiter(redis_host="nonexistent", redis_port=9999)
        allowed, details = limiter.is_allowed("user", rps_limit=10, burst_limit=50)
        passed = "backend" in details
        print_check("New API with explicit rps_limit/burst_limit", passed)
        if passed:
            checks_passed += 1
    except Exception as e:
        print_check("New API with explicit rps_limit/burst_limit", False, str(e))

    print(f"\n  Result: {checks_passed}/{total_checks} checks passed")
    return checks_passed == total_checks


# =============================================================================
# ISSUE #193: N+1 QUERY FIX VERIFICATION
# =============================================================================

def verify_n_plus_one_fixes():
    """Verify N+1 query fixes with eager loading."""
    print_header("Issue #193: N+1 Query Fixes with Eager Loading")

    checks_passed = 0
    total_checks = 0

    # Check 1: SQLAlchemy imports include joinedload/selectinload
    total_checks += 1
    try:
        from sqlalchemy.orm import joinedload, selectinload
        print_check("SQLAlchemy eager loading imports available", True)
        checks_passed += 1
    except ImportError as e:
        print_check("SQLAlchemy eager loading imports available", False, str(e))

    # Check 2: tasks.py uses eager loading
    total_checks += 1
    try:
        with open("src/api/tasks.py", "r") as f:
            content = f.read()
        has_joinedload = "joinedload" in content
        has_selectinload = "selectinload" in content
        has_options = ".options(" in content
        passed = has_joinedload and has_selectinload and has_options
        print_check("tasks.py uses joinedload/selectinload", passed)
        if passed:
            checks_passed += 1
    except Exception as e:
        print_check("tasks.py uses joinedload/selectinload", False, str(e))

    # Check 3: analytics.py uses eager loading
    total_checks += 1
    try:
        with open("src/api/analytics.py", "r") as f:
            content = f.read()
        has_joinedload = "joinedload" in content
        has_selectinload = "selectinload" in content
        passed = has_joinedload and has_selectinload
        print_check("analytics.py uses joinedload/selectinload", passed)
        if passed:
            checks_passed += 1
    except Exception as e:
        print_check("analytics.py uses joinedload/selectinload", False, str(e))

    # Check 4: Task relationships are configured with lazy loading
    total_checks += 1
    try:
        from api.task_models import Task
        # Check that relationships have lazy configuration
        relationships = Task.__mapper__.relationships
        has_joined = any(r.lazy == "joined" for r in relationships)
        has_selectin = any(r.lazy == "selectin" for r in relationships)
        passed = has_joined or has_selectin
        print_check("Task model has eager loading configured", passed)
        if passed:
            checks_passed += 1
    except Exception as e:
        print_check("Task model has eager loading configured", False, str(e))

    # Check 5: Query patterns updated in get_task
    total_checks += 1
    try:
        with open("src/api/tasks.py", "r") as f:
            content = f.read()
        # Check for the pattern of eager loading in get_task
        has_execution = "joinedload(Task.execution)" in content
        has_planning = "joinedload(Task.planning)" in content
        has_review = "joinedload(Task.review)" in content
        has_outputs = "selectinload(Task.outputs)" in content
        passed = has_execution and has_planning and has_review and has_outputs
        print_check("get_task function uses eager loading for all relationships", passed)
        if passed:
            checks_passed += 1
    except Exception as e:
        print_check("get_task function uses eager loading for all relationships", False, str(e))

    print(f"\n  Result: {checks_passed}/{total_checks} checks passed")
    return checks_passed == total_checks


# =============================================================================
# ISSUE #194: DATABASE INDEXES VERIFICATION
# =============================================================================

def verify_database_indexes():
    """Verify database indexes migration."""
    print_header("Issue #194: Database Indexes")

    checks_passed = 0
    total_checks = 0

    # Check 1: Migration file exists
    total_checks += 1
    migration_path = "alembic/versions/001_add_performance_indexes.py"
    exists = os.path.exists(migration_path)
    print_check(f"Migration file exists ({migration_path})", exists)
    if exists:
        checks_passed += 1

    # Check 2: Migration contains Task indexes
    total_checks += 1
    try:
        with open(migration_path, "r") as f:
            content = f.read()
        has_client_email = "idx_tasks_client_email" in content
        has_status = "idx_tasks_status" in content
        has_created_at = "idx_tasks_created_at" in content
        has_composite = "idx_tasks_client_status" in content
        passed = has_client_email and has_status and has_created_at and has_composite
        print_check("Task table indexes defined", passed)
        if passed:
            checks_passed += 1
    except Exception as e:
        print_check("Task table indexes defined", False, str(e))

    # Check 3: Migration contains Bid indexes
    total_checks += 1
    try:
        with open(migration_path, "r") as f:
            content = f.read()
        has_job_id = "idx_bids_job_id" in content
        has_marketplace = "idx_bids_marketplace" in content
        passed = has_job_id and has_marketplace
        print_check("Bid table indexes defined", passed)
        if passed:
            checks_passed += 1
    except Exception as e:
        print_check("Bid table indexes defined", False, str(e))

    # Check 4: Migration contains ClientProfile indexes
    total_checks += 1
    try:
        with open(migration_path, "r") as f:
            content = f.read()
        has_client_email = "idx_client_profiles_client_email" in content
        passed = has_client_email
        print_check("ClientProfile table indexes defined", passed)
        if passed:
            checks_passed += 1
    except Exception as e:
        print_check("ClientProfile table indexes defined", False, str(e))

    # Check 5: Migration contains TaskExecution indexes
    total_checks += 1
    try:
        with open(migration_path, "r") as f:
            content = f.read()
        has_task_id = "idx_task_executions_task_id" in content
        has_status = "idx_task_executions_status" in content
        has_started_at = "idx_task_executions_started_at" in content
        passed = has_task_id and has_status and has_started_at
        print_check("TaskExecution table indexes defined", passed)
        if passed:
            checks_passed += 1
    except Exception as e:
        print_check("TaskExecution table indexes defined", False, str(e))

    # Check 6: Migration has downgrade function
    total_checks += 1
    try:
        with open(migration_path, "r") as f:
            content = f.read()
        has_downgrade = "def downgrade() -> None:" in content
        has_drop_index = "op.drop_index" in content
        passed = has_downgrade and has_drop_index
        print_check("Migration has downgrade function", passed)
        if passed:
            checks_passed += 1
    except Exception as e:
        print_check("Migration has downgrade function", False, str(e))

    # Check 7: Composite indexes defined
    total_checks += 1
    try:
        with open(migration_path, "r") as f:
            content = f.read()
        has_client_status = '["client_email", "status"]' in content
        has_status_created = '["status", "created_at"]' in content
        passed = has_client_status and has_status_created
        print_check("Composite indexes defined (client_id, status), (status, created_at)", passed)
        if passed:
            checks_passed += 1
    except Exception as e:
        print_check("Composite indexes defined", False, str(e))

    print(f"\n  Result: {checks_passed}/{total_checks} checks passed")
    return checks_passed == total_checks


# =============================================================================
# MAIN VERIFICATION
# =============================================================================

def main():
    """Run all verification checks."""
    print("\n" + "=" * 70)
    print("  PERFORMANCE IMPROVEMENTS VERIFICATION")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 70)

    results = {}

    # Run verifications
    results["Issue #192"] = verify_redis_rate_limiter()
    results["Issue #193"] = verify_n_plus_one_fixes()
    results["Issue #194"] = verify_database_indexes()

    # Print summary
    print_header("VERIFICATION SUMMARY")

    all_passed = True
    for issue, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  [{status}] {issue}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("  ALL VERIFICATIONS PASSED ✓")
    else:
        print("  SOME VERIFICATIONS FAILED ✗")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
