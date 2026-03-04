"""
Tests for Redis-based distributed rate limiter (QAQC-009).

Tests cover:
- Redis sliding window rate limiting
- Redis fixed window rate limiting
- In-memory fallback when Redis unavailable
- Distributed behavior simulation
- Rate limit reset functionality
- Usage tracking
- Event recording

Issue QAQC-009: Replace In-Memory Rate Limiting with Redis
"""

import os
import sys
import time
import pytest
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing without Redis server."""
    mock = MagicMock()
    mock.ping = Mock(return_value=True)
    mock.script_load = Mock(side_effect=["sha1", "sha2"])
    mock.evalsha = Mock(return_value=[1, 1])
    mock.zadd = Mock(return_value=1)
    mock.zcard = Mock(return_value=1)
    mock.zremrangebyscore = Mock(return_value=0)
    mock.expire = Mock(return_value=True)
    mock.incr = Mock(return_value=1)
    mock.keys = Mock(return_value=["ratelimit:test:user:1"])
    mock.delete = Mock(return_value=1)
    mock.zcount = Mock(return_value=1)
    
    # Pipeline mock
    pipe_mock = MagicMock()
    pipe_mock.execute = Mock(return_value=[1, 1])
    mock.pipeline = Mock(return_value=pipe_mock)
    
    return mock


@pytest.fixture
def rate_limiter_redis(mock_redis):
    """Rate limiter with mocked Redis."""
    from src.utils.redis_rate_limiter import RedisRateLimiter
    
    with patch('redis.Redis.from_url', return_value=mock_redis):
        limiter = RedisRateLimiter(redis_url="redis://localhost:6379/0")
        # Manually set the mock to avoid connection issues
        limiter._redis = mock_redis
        limiter._script_sha_sliding = "sha1"
        limiter._script_sha_fixed = "sha2"
        yield limiter


@pytest.fixture
def rate_limiter_no_redis():
    """Rate limiter without Redis (in-memory fallback)."""
    from src.utils.redis_rate_limiter import RedisRateLimiter
    
    # Force in-memory by providing invalid Redis URL
    limiter = RedisRateLimiter(redis_url="redis://nonexistent:6379/0")
    return limiter


# ============================================================================
# TESTS: INITIALIZATION
# ============================================================================

class TestRedisRateLimiterInitialization:
    """Test RedisRateLimiter initialization."""

    def test_init_with_url(self, mock_redis):
        """Test initialization with Redis URL."""
        from src.utils.redis_rate_limiter import RedisRateLimiter
        
        with patch('redis.Redis.from_url', return_value=mock_redis):
            limiter = RedisRateLimiter(redis_url="redis://localhost:6379/0")
            assert limiter.is_redis_available

    def test_init_with_individual_params(self, mock_redis):
        """Test initialization with individual Redis parameters."""
        from src.utils.redis_rate_limiter import RedisRateLimiter
        
        with patch('redis.Redis.from_url', return_value=mock_redis):
            limiter = RedisRateLimiter(
                redis_host="localhost",
                redis_port=6379,
                redis_db=0,
            )
            assert limiter.is_redis_available

    def test_init_without_redis(self):
        """Test initialization without Redis (in-memory fallback)."""
        from src.utils.redis_rate_limiter import RedisRateLimiter
        
        limiter = RedisRateLimiter(redis_url="redis://nonexistent:6379/0")
        assert not limiter.is_redis_available

    def test_init_builds_url_from_params(self):
        """Test URL building from individual parameters."""
        from src.utils.redis_rate_limiter import RedisRateLimiter
        
        # Test without password
        limiter = RedisRateLimiter(
            redis_host="testhost",
            redis_port=6380,
            redis_db=1,
            redis_password=None,
        )
        # Just verify it initializes without error
        assert limiter is not None

    def test_init_builds_url_with_password(self):
        """Test URL building with password."""
        from src.utils.redis_rate_limiter import RedisRateLimiter
        
        limiter = RedisRateLimiter(
            redis_host="testhost",
            redis_port=6380,
            redis_db=1,
            redis_password="secret",
        )
        assert limiter is not None


# ============================================================================
# TESTS: SLIDING WINDOW RATE LIMITING
# ============================================================================

class TestSlidingWindowRateLimiting:
    """Test sliding window rate limiting with Redis."""

    def test_allows_within_limit(self, rate_limiter_redis):
        """Test that requests within limit are allowed."""
        allowed, info = rate_limiter_redis.check_rate_limit(
            key="test:user:1",
            max_requests=10,
            window_seconds=60,
            algorithm="sliding",
        )
        
        assert allowed is True
        assert info["allowed"] is True
        assert info["backend"] == "redis_sliding"

    def test_blocks_over_limit(self, rate_limiter_redis, mock_redis):
        """Test that requests over limit are blocked."""
        # Mock to simulate limit exceeded
        mock_redis.evalsha = Mock(return_value=[0, 10])
        
        allowed, info = rate_limiter_redis.check_rate_limit(
            key="test:user:2",
            max_requests=10,
            window_seconds=60,
            algorithm="sliding",
        )
        
        assert allowed is False
        assert info["allowed"] is False
        assert info["retry_after"] > 0

    def test_different_keys_independent(self, rate_limiter_redis):
        """Test that different keys have independent limits."""
        # First key
        allowed1, _ = rate_limiter_redis.check_rate_limit(
            key="test:user:A",
            max_requests=1,
            window_seconds=60,
        )
        
        # Second key should not be affected
        allowed2, _ = rate_limiter_redis.check_rate_limit(
            key="test:user:B",
            max_requests=1,
            window_seconds=60,
        )
        
        assert allowed1 is True
        assert allowed2 is True


# ============================================================================
# TESTS: FIXED WINDOW RATE LIMITING
# ============================================================================

class TestFixedWindowRateLimiting:
    """Test fixed window rate limiting with Redis."""

    def test_allows_within_limit(self, rate_limiter_redis):
        """Test that requests within limit are allowed with fixed window."""
        allowed, info = rate_limiter_redis.check_rate_limit(
            key="test:user:1",
            max_requests=10,
            window_seconds=60,
            algorithm="fixed",
        )
        
        assert allowed is True
        assert info["allowed"] is True
        assert info["backend"] == "redis_fixed"

    def test_blocks_over_limit(self, rate_limiter_redis, mock_redis):
        """Test that requests over limit are blocked with fixed window."""
        # Mock to simulate limit exceeded
        mock_redis.evalsha = Mock(return_value=[0, 11])
        
        allowed, info = rate_limiter_redis.check_rate_limit(
            key="test:user:2",
            max_requests=10,
            window_seconds=60,
            algorithm="fixed",
        )
        
        assert allowed is False
        assert info["allowed"] is False


# ============================================================================
# TESTS: IN-MEMORY FALLBACK
# ============================================================================

class TestInMemoryFallback:
    """Test in-memory fallback when Redis unavailable."""

    def test_allows_within_limit(self, rate_limiter_no_redis):
        """Test that requests within limit are allowed in memory."""
        for i in range(5):
            allowed, info = rate_limiter_no_redis.check_rate_limit(
                key="test:user:1",
                max_requests=10,
                window_seconds=60,
            )
            assert allowed is True
            assert info["backend"] == "memory"

    def test_blocks_over_limit(self, rate_limiter_no_redis):
        """Test that requests over limit are blocked in memory."""
        # Make 10 requests
        for i in range(10):
            rate_limiter_no_redis.check_rate_limit(
                key="test:user:2",
                max_requests=10,
                window_seconds=60,
            )
        
        # 11th request should be blocked
        allowed, info = rate_limiter_no_redis.check_rate_limit(
            key="test:user:2",
            max_requests=10,
            window_seconds=60,
        )
        
        assert allowed is False
        assert info["backend"] == "memory"

    def test_resets_after_window(self, rate_limiter_no_redis):
        """Test that rate limit resets after window expires."""
        # Use very short window
        allowed1, _ = rate_limiter_no_redis.check_rate_limit(
            key="test:user:3",
            max_requests=1,
            window_seconds=1,  # 1 second window
        )
        assert allowed1 is True
        
        # Second request should be blocked
        allowed2, _ = rate_limiter_no_redis.check_rate_limit(
            key="test:user:3",
            max_requests=1,
            window_seconds=1,
        )
        assert allowed2 is False
        
        # Wait for window to expire
        time.sleep(1.5)
        
        # Should be allowed again
        allowed3, _ = rate_limiter_no_redis.check_rate_limit(
            key="test:user:3",
            max_requests=1,
            window_seconds=1,
        )
        assert allowed3 is True


# ============================================================================
# TESTS: RESET FUNCTIONALITY
# ============================================================================

class TestResetFunctionality:
    """Test rate limit reset functionality."""

    def test_reset_with_redis(self, rate_limiter_redis, mock_redis):
        """Test reset with Redis."""
        result = rate_limiter_redis.reset(key="test:user:1")
        assert result is True
        mock_redis.keys.assert_called()

    def test_reset_without_redis(self, rate_limiter_no_redis):
        """Test reset without Redis returns False."""
        result = rate_limiter_no_redis.reset(key="test:user:1")
        assert result is False


# ============================================================================
# TESTS: USAGE TRACKING
# ============================================================================

class TestUsageTracking:
    """Test usage tracking functionality."""

    def test_get_usage_with_redis(self, rate_limiter_redis, mock_redis):
        """Test getting usage with Redis."""
        mock_redis.zcount = Mock(return_value=5)
        
        usage = rate_limiter_redis.get_usage(
            key="test:user:1",
            window_seconds=60,
        )
        
        assert usage["backend"] == "redis"
        assert usage["available"] is True
        assert usage["current_count"] == 5

    def test_get_usage_without_redis(self, rate_limiter_no_redis):
        """Test getting usage without Redis."""
        usage = rate_limiter_no_redis.get_usage(
            key="test:user:1",
            window_seconds=60,
        )
        
        assert usage["available"] is False


# ============================================================================
# TESTS: EVENT RECORDING
# ============================================================================

class TestEventRecording:
    """Test event recording functionality."""

    def test_record_event_with_redis(self, mock_redis):
        """Test recording event with Redis."""
        from src.utils.redis_rate_limiter import RedisRateLimiter
        
        # Setup pipeline mock for record_event
        pipe_mock = MagicMock()
        pipe_mock.zadd = Mock(return_value=1)
        pipe_mock.expire = Mock(return_value=True)
        pipe_mock.execute = Mock(return_value=[1, True])
        mock_redis.pipeline = Mock(return_value=pipe_mock)
        mock_redis.ping = Mock(return_value=True)
        
        with patch('redis.Redis.from_url', return_value=mock_redis):
            limiter = RedisRateLimiter(redis_url="redis://localhost:6379/0")
            limiter._redis = mock_redis
            
            limiter.record_event(
                key="test:user:1",
                event_type="failure",
            )
            
            mock_redis.pipeline.assert_called()
            pipe_mock.zadd.assert_called()

    def test_record_event_without_redis(self, rate_limiter_no_redis):
        """Test recording event without Redis (should not raise)."""
        # Should not raise exception
        rate_limiter_no_redis.record_event(
            key="test:user:1",
            event_type="failure",
        )


# ============================================================================
# TESTS: GLOBAL HELPER FUNCTIONS
# ============================================================================

class TestGlobalHelperFunctions:
    """Test global helper functions."""

    def test_get_rate_limiter_singleton(self):
        """Test that get_rate_limiter returns singleton."""
        from src.utils.redis_rate_limiter import get_rate_limiter, reset_rate_limiter
        
        reset_rate_limiter()  # Reset for clean test
        
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        
        assert limiter1 is limiter2
        
        reset_rate_limiter()  # Clean up

    def test_check_delivery_rate_limit(self, mock_redis):
        """Test check_delivery_rate_limit helper."""
        from src.utils.redis_rate_limiter import check_delivery_rate_limit, reset_rate_limiter
        
        reset_rate_limiter()
        
        with patch('redis.Redis.from_url', return_value=mock_redis):
            with patch.object(mock_redis, 'evalsha', return_value=[1, 1]):
                allowed, info = check_delivery_rate_limit(
                    task_id="test-task-123",
                    max_attempts=5,
                    window_seconds=3600,
                )
                
                assert allowed is True

    def test_check_ip_rate_limit(self, mock_redis):
        """Test check_ip_rate_limit helper."""
        from src.utils.redis_rate_limiter import check_ip_rate_limit, reset_rate_limiter
        
        reset_rate_limiter()
        
        with patch('redis.Redis.from_url', return_value=mock_redis):
            with patch.object(mock_redis, 'evalsha', return_value=[1, 1]):
                allowed, info = check_ip_rate_limit(
                    ip="192.168.1.1",
                    max_attempts=20,
                    window_seconds=3600,
                )
                
                assert allowed is True

    def test_record_delivery_failure(self, mock_redis):
        """Test record_delivery_failure helper."""
        from src.utils.redis_rate_limiter import record_delivery_failure, reset_rate_limiter
        
        reset_rate_limiter()
        
        with patch('redis.Redis.from_url', return_value=mock_redis):
            # Should not raise
            record_delivery_failure(
                task_id="test-task-123",
                ip="192.168.1.1",
            )


# ============================================================================
# TESTS: REDIS ERROR HANDLING
# ============================================================================

class TestRedisErrorHandling:
    """Test Redis error handling."""

    def test_lua_script_error_fallback(self, mock_redis):
        """Test fallback when Lua script fails."""
        from src.utils.redis_rate_limiter import RedisRateLimiter
        from redis.exceptions import RedisError
        
        # Make evalsha fail, then use pipeline fallback
        mock_redis.evalsha = Mock(side_effect=RedisError("NOSCRIPT"))
        mock_redis.script_load = Mock(return_value="sha1")  # Reload succeeds
        
        pipe_mock = MagicMock()
        pipe_mock.execute = Mock(return_value=[0, 1])  # zremrangebyscore, zcard
        mock_redis.pipeline = Mock(return_value=pipe_mock)
        
        with patch('redis.Redis.from_url', return_value=mock_redis):
            limiter = RedisRateLimiter(redis_url="redis://localhost:6379/0")
            limiter._redis = mock_redis
            limiter._script_sha_sliding = None  # Force reload
            
            # Should not raise, should use pipeline fallback
            allowed, info = limiter.check_rate_limit(
                key="test:user:1",
                max_requests=10,
                window_seconds=60,
            )
            
            # Should still work via pipeline fallback
            assert allowed is True

    def test_redis_connection_error_allows_request(self):
        """Test that Redis connection errors allow requests (fail-open)."""
        from src.utils.redis_rate_limiter import RedisRateLimiter
        
        limiter = RedisRateLimiter(redis_url="redis://nonexistent:6379/0")
        
        # Should not raise, should allow request via in-memory fallback
        # Use high max_requests to ensure first request is allowed
        allowed, info = limiter.check_rate_limit(
            key="test:user:1",
            max_requests=100,  # High limit
            window_seconds=60,
        )
        
        # In-memory fallback should allow the first request
        assert allowed is True
        assert info["backend"] == "memory"


# ============================================================================
# TESTS: DISTRIBUTED BEHAVIOR SIMULATION
# ============================================================================

class TestDistributedBehavior:
    """Test distributed behavior simulation."""

    def test_same_key_shared_across_instances(self, mock_redis):
        """Test that same key is shared across limiter instances."""
        from src.utils.redis_rate_limiter import RedisRateLimiter
        
        # Create two limiter instances with same mock
        with patch('redis.Redis.from_url', return_value=mock_redis):
            limiter1 = RedisRateLimiter(redis_url="redis://localhost:6379/0")
            limiter1._redis = mock_redis
            limiter1._script_sha_sliding = "sha1"
            
        with patch('redis.Redis.from_url', return_value=mock_redis):
            limiter2 = RedisRateLimiter(redis_url="redis://localhost:6379/0")
            limiter2._redis = mock_redis
            limiter2._script_sha_sliding = "sha1"
            
            # Both should use same Redis backend
            assert limiter1.is_redis_available
            assert limiter2.is_redis_available
            
            # Both should make requests to same key
            limiter1.check_rate_limit("shared:key", 10, 60)
            limiter2.check_rate_limit("shared:key", 10, 60)
            
            # Verify Redis was called twice for same key
            assert mock_redis.evalsha.call_count == 2


# ============================================================================
# TESTS: KEY PREFIX
# ============================================================================

class TestKeyPrefix:
    """Test key prefix functionality."""

    def test_custom_key_prefix(self, mock_redis):
        """Test custom key prefix."""
        from src.utils.redis_rate_limiter import RedisRateLimiter
        
        mock_redis.ping = Mock(return_value=True)
        mock_redis.script_load = Mock(side_effect=["sha1", "sha2"])
        mock_redis.evalsha = Mock(return_value=[1, 1])
        
        with patch('redis.Redis.from_url', return_value=mock_redis):
            limiter = RedisRateLimiter(
                redis_url="redis://localhost:6379/0",
                key_prefix="custom_prefix",
            )
            
            limiter.check_rate_limit("test:key", 10, 60)
            
            # Verify key includes custom prefix
            call_args = mock_redis.evalsha.call_args
            # KEYS[1] is the first argument after the script SHA
            key_arg = call_args[0][1]  # Second positional arg (KEYS[1])
            assert "custom_prefix:test:key" in str(key_arg) or "custom_prefix" in str(call_args)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
