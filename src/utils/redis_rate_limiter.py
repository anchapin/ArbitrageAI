"""
Redis-backed distributed rate limiter for ArbitrageAI.

Issue QAQC-009: Replace In-Memory Rate Limiting with Redis
Issue #45: API Rate Limiting, Quotas, and Usage Analytics
Issue #192: Redis-based Rate Limiting

Provides:
- Distributed rate limiting using Redis sorted sets (sliding window)
- Fixed window rate limiting using Redis INCR with TTL
- Atomic operations using Lua scripts
- Graceful fallback to in-memory limiting when Redis unavailable
- Support for multiple rate limit keys (task-based, IP-based, user-based)

Features:
- Atomic Redis operations ensure consistency across distributed workers
- Sliding window algorithm for accurate rate limiting
- Automatic cleanup of expired keys
- Memory-efficient storage using sorted sets
- Configurable windows and limits per use case

Usage:
    from src.utils.redis_rate_limiter import RedisRateLimiter

    limiter = RedisRateLimiter()
    allowed, info = limiter.check_rate_limit(
        key="delivery:task:123",
        max_requests=5,
        window_seconds=3600,
    )
"""

import logging
import os
import time
from typing import Any

import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


# Lua script for sliding window rate limiting using sorted sets
# This provides accurate rate limiting across distributed workers
SLIDING_WINDOW_LUA_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

-- Remove old entries outside the window
local window_start = now - window
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- Count current requests in window
local current_count = redis.call('ZCARD', key)

-- Check if limit exceeded
if current_count >= limit then
    return {0, current_count}
end

-- Add new request with current timestamp as score
redis.call('ZADD', key, now, member)

-- Set expiry on the key (window + buffer)
redis.call('EXPIRE', key, window + 1)

return {1, current_count + 1}
"""

# Lua script for fixed window rate limiting using INCR
# Simpler and faster for coarse-grained limiting
FIXED_WINDOW_LUA_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])

local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, ttl)
end

if current > limit then
    return {0, current}
else
    return {1, current}
end
"""


class RedisRateLimiter:
    """
    Distributed rate limiter using Redis.

    Supports two algorithms:
    1. Sliding window (using sorted sets) - accurate, recommended for fine-grained limiting
    2. Fixed window (using INCR) - faster, good for coarse-grained limiting

    Features:
    - Atomic operations via Lua scripts
    - Distributed across multiple workers
    - Automatic cleanup of expired keys
    - Graceful fallback to in-memory when Redis unavailable
    """

    # Class-level storage for in-memory fallback
    _in_memory_windows: dict[str, dict[str, Any]] = {}

    def __init__(
        self,
        redis_url: str | None = None,
        redis_host: str | None = None,
        redis_port: int | None = None,
        redis_db: int | None = None,
        redis_password: str | None = None,
        default_ttl: int = 2,
        key_prefix: str = "ratelimit",
    ):
        """
        Initialize Redis rate limiter.

        Args:
            redis_url: Complete Redis URL (takes priority)
            redis_host: Redis host (used if redis_url not provided)
            redis_port: Redis port (used if redis_url not provided)
            redis_db: Redis database number (used if redis_url not provided)
            redis_password: Redis password (used if redis_url not provided)
            default_ttl: Default TTL for rate limit keys in seconds
            key_prefix: Prefix for all rate limit keys
        """
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self._redis: redis.Redis | None = None
        self._script_sha_sliding: str | None = None
        self._script_sha_fixed: str | None = None

        # Build Redis URL from parameters
        self._redis_url = redis_url or self._build_redis_url(
            redis_host, redis_port, redis_db, redis_password,
        )

        # Try to connect to Redis
        self._connect()

    def _build_redis_url(
        self,
        host: str | None,
        port: int | None,
        db: int | None,
        password: str | None,
    ) -> str:
        """Build Redis URL from individual parameters."""
        host = host or os.getenv("REDIS_HOST", "localhost")
        port = port or int(os.getenv("REDIS_PORT", 6379))
        db = db or int(os.getenv("REDIS_DB", 0))
        password = password or os.getenv("REDIS_PASSWORD")

        if password:
            return f"redis://:{password}@{host}:{port}/{db}"
        return f"redis://{host}:{port}/{db}"

    def _connect(self) -> None:
        """Establish Redis connection with retry logic."""
        try:
            self._redis = redis.Redis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )

            # Test connection
            self._redis.ping()

            # Load Lua scripts
            self._load_scripts()

            logger.info(f"Redis rate limiter connected to {self._redis_url}")

        except RedisError as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory fallback.")
            self._redis = None
        except Exception as e:
            logger.warning(f"Unexpected error connecting to Redis: {e}. Using in-memory fallback.")
            self._redis = None

    def _load_scripts(self) -> None:
        """Load Lua scripts into Redis and cache their SHA hashes."""
        if self._redis:
            try:
                self._script_sha_sliding = self._redis.script_load(SLIDING_WINDOW_LUA_SCRIPT)
                self._script_sha_fixed = self._redis.script_load(FIXED_WINDOW_LUA_SCRIPT)
                logger.debug("Lua scripts loaded successfully")
            except RedisError as e:
                logger.warning(f"Failed to load Lua scripts: {e}. Will use pipeline approach.")
                self._script_sha_sliding = None
                self._script_sha_fixed = None

    @property
    def is_redis_available(self) -> bool:
        """Check if Redis is available."""
        if self._redis is None:
            return False
        try:
            self._redis.ping()
            return True
        except RedisError:
            return False

    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        algorithm: str = "sliding",
    ) -> tuple[bool, dict[str, Any]]:
        """
        Check if request is within rate limit.

        Args:
            key: Unique identifier (e.g., "delivery:task:123" or "delivery:ip:192.168.1.1")
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
            algorithm: "sliding" for sliding window, "fixed" for fixed window

        Returns:
            Tuple of (allowed: bool, info: dict)
            info contains: allowed, current_count, max_requests, window_seconds, retry_after, backend
        """
        if self._redis and self.is_redis_available:
            if algorithm == "fixed":
                return self._check_fixed_window(key, max_requests, window_seconds)
            return self._check_sliding_window(key, max_requests, window_seconds)
        return self._check_memory(key, max_requests, window_seconds)

    def _check_sliding_window(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Check rate limit using sliding window algorithm with sorted sets.

        This is the most accurate algorithm for distributed rate limiting.
        """
        try:
            current_time = time.time()
            redis_key = f"{self.key_prefix}:{key}"
            member = f"{current_time}:{os.urandom(4).hex()}"

            # Try Lua script first (atomic operation)
            if self._script_sha_sliding:
                try:
                    result = self._redis.evalsha(
                        self._script_sha_sliding,
                        1,
                        redis_key,
                        current_time,
                        window_seconds,
                        max_requests,
                        member,
                    )
                    allowed = bool(result[0])
                    current_count = int(result[1])

                    return allowed, {
                        "allowed": allowed,
                        "current_count": current_count,
                        "max_requests": max_requests,
                        "window_seconds": window_seconds,
                        "retry_after": window_seconds if not allowed else 0,
                        "backend": "redis_sliding",
                    }
                except RedisError as e:
                    # Script might have been flushed, reload it
                    logger.debug(f"Lua script error, reloading: {e}")
                    self._load_scripts()
                    # Fall through to pipeline approach

            # Fallback to pipeline approach
            window_start = current_time - window_seconds

            pipe = self._redis.pipeline(transaction=True)
            pipe.zremrangebyscore(redis_key, "-inf", window_start)
            pipe.zcard(redis_key)
            results = pipe.execute()

            current_count = results[1]

            if current_count >= max_requests:
                return False, {
                    "allowed": False,
                    "current_count": current_count,
                    "max_requests": max_requests,
                    "window_seconds": window_seconds,
                    "retry_after": window_seconds,
                    "backend": "redis_sliding",
                }

            # Add new request
            pipe = self._redis.pipeline(transaction=True)
            pipe.zadd(redis_key, {member: current_time})
            pipe.expire(redis_key, window_seconds + 1)
            pipe.execute()

            return True, {
                "allowed": True,
                "current_count": current_count + 1,
                "max_requests": max_requests,
                "window_seconds": window_seconds,
                "retry_after": 0,
                "backend": "redis_sliding",
            }

        except RedisError as e:
            logger.error(f"Redis sliding window rate limit check failed: {e}. Allowing request.")
            return True, {
                "allowed": True,
                "reason": "redis_error",
                "error": str(e),
                "backend": "redis_error",
            }

    def _check_fixed_window(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Check rate limit using fixed window algorithm with INCR.

        This is faster but less accurate than sliding window.
        Good for coarse-grained rate limiting.
        """
        try:
            current_window = int(time.time() // window_seconds)
            redis_key = f"{self.key_prefix}:{key}:{current_window}"

            # Try Lua script first
            if self._script_sha_fixed:
                try:
                    result = self._redis.evalsha(
                        self._script_sha_fixed,
                        1,
                        redis_key,
                        max_requests,
                        window_seconds * 2,  # TTL with buffer
                    )
                    allowed = bool(result[0])
                    current_count = int(result[1])

                    return allowed, {
                        "allowed": allowed,
                        "current_count": current_count,
                        "max_requests": max_requests,
                        "window_seconds": window_seconds,
                        "retry_after": window_seconds if not allowed else 0,
                        "backend": "redis_fixed",
                    }
                except RedisError as e:
                    logger.debug(f"Lua script error, reloading: {e}")
                    self._load_scripts()

            # Fallback to pipeline approach
            pipe = self._redis.pipeline(transaction=True)
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_seconds * 2)
            results = pipe.execute()

            current_count = results[0]
            allowed = current_count <= max_requests

            return allowed, {
                "allowed": allowed,
                "current_count": current_count,
                "max_requests": max_requests,
                "window_seconds": window_seconds,
                "retry_after": window_seconds if not allowed else 0,
                "backend": "redis_fixed",
            }

        except RedisError as e:
            logger.error(f"Redis fixed window rate limit check failed: {e}. Allowing request.")
            return True, {
                "allowed": True,
                "reason": "redis_error",
                "error": str(e),
                "backend": "redis_error",
            }

    def _check_memory(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Check rate limit using in-memory window (fallback).

        This is used when Redis is unavailable. Note that this does NOT
        provide distributed rate limiting across workers.
        """
        current_time = time.time()
        window_key = f"{key}:{int(current_time // window_seconds)}"

        # Cleanup old windows (prevent memory leak)
        self._cleanup_memory_windows(window_seconds)

        # Get or create window entry
        if window_key not in self._in_memory_windows:
            self._in_memory_windows[window_key] = {
                "count": 0,
                "created_at": current_time,
            }

        # Increment counter
        self._in_memory_windows[window_key]["count"] += 1
        current_count = self._in_memory_windows[window_key]["count"]

        allowed = current_count <= max_requests

        return allowed, {
            "allowed": allowed,
            "current_count": current_count,
            "max_requests": max_requests,
            "window_seconds": window_seconds,
            "retry_after": window_seconds if not allowed else 0,
            "backend": "memory",
        }

    def _cleanup_memory_windows(self, window_seconds: int) -> None:
        """Remove expired in-memory windows to prevent memory leak."""
        cutoff = time.time() - window_seconds - 1
        expired_keys = [
            k for k, v in self._in_memory_windows.items()
            if v["created_at"] < cutoff
        ]
        for k in expired_keys:
            del self._in_memory_windows[k]

    def reset(self, key: str) -> bool:
        """
        Reset rate limit counters for a key.

        Args:
            key: The rate limit key to reset

        Returns:
            True if reset successful, False otherwise
        """
        if not self._redis or not self.is_redis_available:
            return False

        try:
            # Delete all keys matching the pattern
            pattern = f"{self.key_prefix}:{key}*"
            keys = self._redis.keys(pattern)
            if keys:
                self._redis.delete(*keys)
            return True
        except RedisError as e:
            logger.error(f"Failed to reset rate limit: {e}")
            return False

    def get_usage(self, key: str, window_seconds: int) -> dict[str, Any]:
        """
        Get current rate limit usage for a key.

        Args:
            key: The rate limit key
            window_seconds: The window size (for sliding window)

        Returns:
            Dict with usage information
        """
        if not self._redis or not self.is_redis_available:
            return {"backend": "memory", "available": False}

        try:
            current_time = time.time()
            redis_key = f"{self.key_prefix}:{key}"
            window_start = current_time - window_seconds

            # Count requests in current window
            count = self._redis.zcount(redis_key, window_start, current_time)

            return {
                "backend": "redis",
                "available": True,
                "current_count": count,
                "window_seconds": window_seconds,
            }
        except RedisError as e:
            logger.error(f"Failed to get usage: {e}")
            return {"backend": "redis", "available": False, "error": str(e)}

    def record_event(
        self,
        key: str,
        event_type: str = "request",
    ) -> None:
        """
        Record an event without checking the limit.

        Useful for tracking failures or other events separately.

        Args:
            key: The rate limit key
            event_type: Type of event (e.g., "failure", "success")
        """
        if not self._redis or not self.is_redis_available:
            return

        try:
            current_time = time.time()
            redis_key = f"{self.key_prefix}:{key}:{event_type}"
            member = f"{current_time}:{os.urandom(4).hex()}"

            pipe = self._redis.pipeline(transaction=True)
            pipe.zadd(redis_key, {member: current_time})
            pipe.expire(redis_key, 3600)  # 1 hour TTL for events
            pipe.execute()
        except RedisError as e:
            logger.error(f"Failed to record event: {e}")


# Global instance for singleton pattern
_rate_limiter: RedisRateLimiter | None = None


def get_rate_limiter(
    redis_url: str | None = None,
    key_prefix: str = "ratelimit",
) -> RedisRateLimiter:
    """
    Get or create global rate limiter instance.

    Args:
        redis_url: Optional Redis URL override
        key_prefix: Optional key prefix override

    Returns:
        RedisRateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        # Try to get Redis URL from config or environment
        config_redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _rate_limiter = RedisRateLimiter(redis_url=config_redis_url, key_prefix=key_prefix)
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter instance. Useful for testing."""
    global _rate_limiter
    _rate_limiter = None


# Convenience functions for common use cases
def check_delivery_rate_limit(
    task_id: str,
    max_attempts: int = 5,
    window_seconds: int = 3600,
) -> tuple[bool, dict[str, Any]]:
    """
    Check delivery rate limit for a task.

    Args:
        task_id: The task UUID
        max_attempts: Maximum failed attempts allowed
        window_seconds: Lockout window in seconds

    Returns:
        Tuple of (allowed: bool, info: dict)
    """
    limiter = get_rate_limiter()
    key = f"delivery:task:{task_id}"
    return limiter.check_rate_limit(key, max_attempts, window_seconds, algorithm="sliding")


def check_ip_rate_limit(
    ip: str,
    max_attempts: int = 20,
    window_seconds: int = 3600,
) -> tuple[bool, dict[str, Any]]:
    """
    Check delivery rate limit for an IP address.

    Args:
        ip: The client IP address
        max_attempts: Maximum attempts allowed
        window_seconds: Lockout window in seconds

    Returns:
        Tuple of (allowed: bool, info: dict)
    """
    limiter = get_rate_limiter()
    key = f"delivery:ip:{ip}"
    return limiter.check_rate_limit(key, max_attempts, window_seconds, algorithm="sliding")


def record_delivery_failure(
    task_id: str,
    ip: str | None = None,
) -> None:
    """
    Record a delivery failure for rate limiting.

    Args:
        task_id: The task UUID
        ip: Optional client IP address
    """
    limiter = get_rate_limiter()

    # Record task failure
    task_key = f"delivery:task:{task_id}"
    limiter.record_event(task_key, "failure")

    # Record IP failure if provided
    if ip:
        ip_key = f"delivery:ip:{ip}"
        limiter.record_event(ip_key, "failure")
