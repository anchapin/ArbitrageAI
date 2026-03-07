"""
Performance Improvements Verification Tests

Issue #192: Redis-based Rate Limiting
Issue #193: N+1 Query Fixes with Eager Loading
Issue #194: Database Indexes

This module provides comprehensive tests and verification for the
performance improvements implemented in issues #192, #193, and #194.
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Import rate limiter
from api.rate_limiter import RateLimiter, RedisRateLimiter, QuotaManager
from api.models import (
    Base, Task, TaskExecution, TaskPlanning, TaskReview, TaskOutput,
    Bid, ClientProfile, UserQuota, QuotaUsage, PricingTier, TaskStatus,
    ExecutionStatus, PlanningStatus, ReviewStatus, OutputType,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def test_db():
    """Create in-memory SQLite database for testing."""
    from src.api.marketplace_models import Base as MarketplaceBase
=======
>>>>>>> 0b75a45 (fix: Add missing database tables to test fixtures)
    
    engine = create_engine("sqlite:///:memory:", echo=False)
    
    # Create all tables from all model bases
    Base.metadata.create_all(engine)
    UserBase.metadata.create_all(engine)
>>>>>>> 0b75a45 (fix: Add missing database tables to test fixtures)
    
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user_quota():
    """Create test UserQuota."""
    return UserQuota(
        user_id="test_user_123",
        tier=PricingTier.PRO,
        rate_limit_rps=50,
        rate_limit_burst=200,
        monthly_task_limit=1000,
        monthly_api_calls_limit=10000,
    )


@pytest.fixture
def test_task():
    """Create test Task."""
    return Task(
        id="test_task_123",
        title="Test Task",
        description="Test Description",
        domain="data_entry",
        status=TaskStatus.PAID,
        client_email="test@example.com",
        amount_paid=5000,
    )


# =============================================================================
# ISSUE #192: REDIS RATE LIMITING TESTS
# =============================================================================

class TestRedisRateLimiter:
    """Tests for Redis-based rate limiter (Issue #192)."""

    def test_redis_rate_limiter_initialization_no_redis(self):
        """Test rate limiter initializes gracefully without Redis."""
        with patch.dict(os.environ, {"REDIS_HOST": "nonexistent"}):
            limiter = RedisRateLimiter(
                redis_host="nonexistent",
                redis_port=9999,
            )
            assert limiter._redis is None
            assert not limiter.is_redis_available

    def test_in_memory_fallback(self):
        """Test in-memory fallback when Redis unavailable."""
        limiter = RedisRateLimiter()
        limiter._redis = None  # Force in-memory mode

        # First request should be allowed
        allowed, details = limiter.is_allowed("user_1", rps_limit=10, burst_limit=50)
        assert allowed is True
        assert details["backend"] == "memory"
        assert details["requests_in_window"] == 1

        # Multiple requests within limit
        for i in range(9):
            allowed, _ = limiter.is_allowed("user_1", rps_limit=10, burst_limit=50)
            assert allowed is True

        # Request exceeding limit should be denied
        allowed, details = limiter.is_allowed("user_1", rps_limit=10, burst_limit=50)
        assert allowed is False
        assert details["requests_in_window"] == 11

    def test_rate_limiter_backward_compatibility(self):
        """Test RateLimiter maintains backward compatibility with UserQuota API."""
        limiter = RateLimiter()
        limiter._redis = None  # Force in-memory mode

        quota = UserQuota(
            user_id="test_user",
            tier=PricingTier.FREE,
            rate_limit_rps=10,
            rate_limit_burst=50,
        )

        # Test with quota parameter (original API)
        allowed, details = limiter.is_allowed("test_user", quota=quota)
        assert allowed is True

        # Test with override
        allowed, details = limiter.is_allowed("test_user", quota=quota, override=True)
        assert allowed is True
        assert details["reason"] == "admin_override"

        # Test with Enterprise tier (no limiting)
        enterprise_quota = UserQuota(
            user_id="enterprise_user",
            tier=PricingTier.ENTERPRISE,
        )
        allowed, details = limiter.is_allowed("enterprise_user", quota=enterprise_quota)
        assert allowed is True
        assert details["reason"] == "enterprise_unlimited"

    def test_memory_cleanup(self):
        """Test that old in-memory windows are cleaned up."""
        limiter = RedisRateLimiter(default_ttl=1)
        limiter._redis = None

        # Create some windows
        for i in range(100):
            limiter.is_allowed(f"user_{i}", rps_limit=10)

        initial_count = len(limiter._in_memory_windows)
        assert initial_count == 100

        # Wait for TTL to expire
        time.sleep(2)

        # Trigger cleanup
        limiter.is_allowed("new_user", rps_limit=10)

        # Old windows should be cleaned up
        assert len(limiter._in_memory_windows) < initial_count

    def test_reset_functionality(self):
        """Test rate limit reset functionality."""
        limiter = RateLimiter()
        limiter._redis = None  # Force in-memory mode

        # Make some requests
        for _ in range(5):
            limiter.is_allowed("reset_user", rps_limit=10)

        # Reset should return False for in-memory (no Redis)
        result = limiter.reset("reset_user")
        assert result is False


class TestQuotaManager:
    """Tests for QuotaManager."""

    def test_get_current_billing_month(self):
        """Test billing month calculation."""
        manager = QuotaManager()
        month = manager.get_current_billing_month()
        assert len(month) == 7  # YYYY-MM format
        assert month[4] == "-"

    def test_check_task_quota(self, test_db, test_user_quota):
        """Test task quota checking."""
        manager = QuotaManager()

        # Should allow when under limit
        allowed, details = manager.check_task_quota(
            test_db, "test_user_123", test_user_quota
        )
        assert allowed is True
        assert details["used"] == 0
        assert details["limit"] == 1000

    def test_increment_task_count(self, test_db):
        """Test task count increment."""
        manager = QuotaManager()

        # Increment twice
        manager.increment_task_count(test_db, "test_user")
        manager.increment_task_count(test_db, "test_user")

        # Verify count
        usage = test_db.query(QuotaUsage).filter(
            QuotaUsage.user_id == "test_user"
        ).first()
        assert usage is not None
        assert usage.task_count == 2


# =============================================================================
# ISSUE #193: N+1 QUERY FIX TESTS
# =============================================================================

class TestEagerLoading:
    """Tests for N+1 query fixes with eager loading (Issue #193)."""

    def test_task_with_relationships(self, test_db, test_task):
        """Test that Task relationships are properly loaded."""
        # Create related entities
        execution = TaskExecution(
            task_id=test_task.id,
            status=ExecutionStatus.COMPLETED,
        )
        planning = TaskPlanning(
            task_id=test_task.id,
            status=PlanningStatus.APPROVED,
            plan_content="Test plan",
        )
        review = TaskReview(
            task_id=test_task.id,
            status=ReviewStatus.RESOLVED,
            approved=True,
        )
        output = TaskOutput(
            task_id=test_task.id,
            output_type=OutputType.IMAGE,
            output_url="http://example.com/image.png",
        )

        test_db.add_all([test_task, execution, planning, review, output])
        test_db.commit()

        # Query with eager loading (simulating the fixed code)
        from sqlalchemy.orm import joinedload, selectinload

        task = (
            test_db.query(Task)
            .filter(Task.id == test_task.id)
            .options(
                joinedload(Task.execution),
                joinedload(Task.planning),
                joinedload(Task.review),
                joinedload(Task.arena),
                selectinload(Task.outputs),
            )
            .first()
        )

        # Verify relationships are loaded
        assert task is not None
        assert task.execution is not None
        assert task.planning is not None
        assert task.review is not None
        assert len(task.outputs) == 1

    def test_to_dict_includes_relationships(self, test_db, test_task):
        """Test that to_dict includes relationship data."""
        # Create related entities
        execution = TaskExecution(task_id=test_task.id, status=ExecutionStatus.COMPLETED)
        test_db.add_all([test_task, execution])
        test_db.commit()

        # Query with eager loading
        from sqlalchemy.orm import joinedload

        task = (
            test_db.query(Task)
            .filter(Task.id == test_task.id)
            .options(joinedload(Task.execution))
            .first()
        )

        # Convert to dict
        task_dict = task.to_dict()

        # Verify nested data is included
        assert "execution" in task_dict
        assert task_dict["execution"]["status"] == "COMPLETED"


# =============================================================================
# ISSUE #194: DATABASE INDEX VERIFICATION
# =============================================================================

class TestDatabaseIndexes:
    """Tests for database indexes (Issue #194)."""

    def test_task_indexes_exist(self, test_db):
        """Verify Task table indexes are created."""
        # Create tables with indexes
        Base.metadata.create_all(test_db.get_bind())

        # Query for indexes (SQLite-specific)
        result = test_db.execute(
            text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tasks'")
        )
        indexes = [row[0] for row in result.fetchall()]

        # Check for expected indexes
        expected_indexes = [
            "idx_task_client_email",
            "idx_task_status",
            "idx_task_created_at",
            "idx_task_client_status",
            "idx_task_status_created",
        ]

        for idx in expected_indexes:
            assert idx in indexes, f"Expected index {idx} not found"

    def test_bid_indexes_exist(self, test_db):
        """Verify Bid table indexes are created."""
        Base.metadata.create_all(test_db.get_bind())

        result = test_db.execute(
            text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='bids'")
        )
        indexes = [row[0] for row in result.fetchall()]

        expected_indexes = [
            "idx_bid_posting_id",
            "idx_bid_status",
            "idx_bid_created_at",
            "idx_bid_marketplace_status",
        ]

        for idx in expected_indexes:
            assert idx in indexes, f"Expected index {idx} not found"

    def test_client_profile_indexes_exist(self, test_db):
        """Verify ClientProfile table indexes are created."""
        Base.metadata.create_all(test_db.get_bind())

        result = test_db.execute(
            text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='client_profiles'")
        )
        indexes = [row[0] for row in result.fetchall()]

        assert "idx_client_profiles_client_email" in indexes


# =============================================================================
# PERFORMANCE BENCHMARK TESTS
# =============================================================================

class TestPerformanceBenchmarks:
    """Performance benchmark tests."""

    def test_rate_limiter_performance(self):
        """Benchmark rate limiter performance."""
        limiter = RateLimiter()
        limiter._redis = None  # Use in-memory for consistent benchmarking

        start_time = time.time()
        iterations = 10000

        for i in range(iterations):
            limiter.is_allowed(f"bench_user_{i % 100}", rps_limit=100)

        elapsed = time.time() - start_time
        ops_per_second = iterations / elapsed

        # Should handle at least 1000 ops/second
        assert ops_per_second > 1000, f"Rate limiter too slow: {ops_per_second:.0f} ops/s"

    def test_query_performance_with_indexes(self, test_db):
        """Benchmark query performance with indexes."""
        # Create test data
        tasks = [
            Task(
                id=f"perf_task_{i}",
                title=f"Task {i}",
                description="Test",
                domain="data_entry",
                status=TaskStatus.PAID if i % 2 == 0 else TaskStatus.COMPLETED,
                client_email=f"user{i}@example.com",
                created_at=datetime.now(timezone.utc) - timedelta(days=i % 30),
            )
            for i in range(1000)
        ]
        test_db.add_all(tasks)
        test_db.commit()

        # Benchmark indexed query
        start_time = time.time()
        iterations = 100

        for _ in range(iterations):
            test_db.query(Task).filter(
                Task.status == TaskStatus.PAID,
                Task.client_email.like("user%@example.com"),
            ).all()

        elapsed = time.time() - start_time
        ops_per_second = iterations / elapsed

        # Should handle at least 10 ops/second (conservative for SQLite)
        assert ops_per_second > 10, f"Query too slow: {ops_per_second:.2f} ops/s"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for all performance improvements."""

    def test_full_task_flow_with_eager_loading(self, test_db):
        """Test complete task flow with optimized queries."""
        # Create task with all relationships
        task = Task(
            id="integration_task",
            title="Integration Test",
            description="Full flow test",
            domain="data_entry",
            status=TaskStatus.PAID,
            client_email="integration@example.com",
            amount_paid=10000,
        )
        execution = TaskExecution(task_id=task.id, status=ExecutionStatus.RUNNING)
        planning = TaskPlanning(task_id=task.id, status=PlanningStatus.GENERATING)
        review = TaskReview(task_id=task.id, status=ReviewStatus.PENDING)

        test_db.add_all([task, execution, planning, review])
        test_db.commit()

        # Simulate the optimized query from tasks.py
        from sqlalchemy.orm import joinedload, selectinload

        loaded_task = (
            test_db.query(Task)
            .filter(Task.id == task.id)
            .options(
                joinedload(Task.execution),
                joinedload(Task.planning),
                joinedload(Task.review),
                joinedload(Task.arena),
                selectinload(Task.outputs),
            )
            .first()
        )

        # Verify all data is accessible without additional queries
        assert loaded_task.title == "Integration Test"
        assert loaded_task.execution.status == ExecutionStatus.RUNNING
        assert loaded_task.planning.status == PlanningStatus.GENERATING
        assert loaded_task.review.status == ReviewStatus.PENDING

        # Verify to_dict works correctly
        task_dict = loaded_task.to_dict()
        assert task_dict["title"] == "Integration Test"
        assert "execution" in task_dict
        assert "planning" in task_dict
        assert "review" in task_dict


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
