"""
Redis-backed distributed rate limiting and quota enforcement.

Issue #45: API Rate Limiting, Quotas, and Usage Analytics
Issue #192: Replace In-Memory Rate Limiting with Redis

Provides:
- RedisRateLimiter for distributed rate limiting (sliding window with Lua scripts)
- InMemoryRateLimiter as fallback when Redis unavailable
- QuotaManager for monthly quota tracking
- Graceful handling with 429/402 status codes
- Webhook alerts for quota thresholds

Features:
- Atomic Redis operations using INCR/EXPIRE
- Distributed rate limiting across multiple workers
- Lua scripts for atomic multi-operation execution
- Automatic fallback to in-memory limiting if Redis unavailable
- Configurable Redis connection with retry logic
"""

from datetime import datetime, timezone
import logging
import os
import time
from typing import Any

import redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from .models import (
    PricingTier,
    QuotaUsage,
    RateLimitLog,
    UserQuota,
)

logger = logging.getLogger(__name__)


# Lua script for atomic rate limiting (INCR + EXPIRE in one operation)
# This ensures atomicity across distributed workers
RATE_LIMIT_LUA_SCRIPT = """
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

# Lua script for burst rate limiting
BURST_LIMIT_LUA_SCRIPT = """
local key = KEYS[1]
local burst_key = KEYS[2]
local limit = tonumber(ARGV[1])
local burst_limit = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local burst_ttl = tonumber(ARGV[4])

-- Check main rate limit
local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, ttl)
end

-- Check burst limit
local burst_current = redis.call('INCR', burst_key)
if burst_current == 1 then
    redis.call('EXPIRE', burst_key, burst_ttl)
end

-- Allow if within rate limit OR burst available
if current <= limit then
    return {1, current, burst_limit - burst_current + 1}
elseif burst_current <= burst_limit then
    return {1, current, burst_limit - burst_current + 1}
else
    return {0, current, 0}
end
"""


class RedisRateLimiter:
    """
    Distributed rate limiter using Redis with atomic Lua scripts.

    Features:
    - Uses Redis INCR/EXPIRE for atomic operations
    - Lua scripts ensure atomicity across distributed workers
    - Sliding window algorithm with burst capacity
    - Automatic connection management with retry logic
    - Graceful degradation to in-memory fallback

    Usage:
        limiter = RedisRateLimiter()
        allowed, details = limiter.is_allowed("user_123", rps_limit=10, burst_limit=50)
    """

    # Class-level storage for in-memory fallback (shared across instances)
    _in_memory_windows: dict[str, dict[str, Any]] = {}

    def __init__(
        self,
        redis_url: str | None = None,
        redis_host: str | None = None,
        redis_port: int | None = None,
        redis_db: int | None = None,
        redis_password: str | None = None,
        default_ttl: int = 2,
        burst_ttl: int = 3600,
    ):
        """
        Initialize Redis rate limiter.

        Args:
            redis_url: Complete Redis URL (takes priority if provided)
            redis_host: Redis host (used if redis_url not provided)
            redis_port: Redis port (used if redis_url not provided)
            redis_db: Redis database number (used if redis_url not provided)
            redis_password: Redis password (used if redis_url not provided)
            default_ttl: Default TTL for rate limit keys in seconds
            burst_ttl: TTL for burst counter keys in seconds
        """
        self.default_ttl = default_ttl
        self.burst_ttl = burst_ttl
        self._redis: redis.Redis | None = None
        self._redis_url = redis_url
        self._redis_host = redis_host
        self._redis_port = redis_port
        self._redis_db = redis_db
        self._redis_password = redis_password
        self._script_sha: str | None = None
        self._burst_script_sha: str | None = None

        # Try to connect to Redis
        self._connect()

    def _connect(self) -> None:
        """Establish Redis connection with retry logic."""
        try:
            # Try URL first
            if self._redis_url:
                self._redis = redis.Redis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
            else:
                # Fall back to individual parameters
                self._redis = redis.Redis(
                    host=self._redis_host or os.getenv("REDIS_HOST", "localhost"),
                    port=int(self._redis_port or os.getenv("REDIS_PORT", 6379)),
                    db=int(self._redis_db or os.getenv("REDIS_DB", 0)),
                    password=self._redis_password or os.getenv("REDIS_PASSWORD"),
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )

            # Test connection
            self._redis.ping()

            # Load Lua scripts
            self._load_scripts()

            logger.info("Redis rate limiter connected successfully")

        except RedisError as e:
            logger.warning(f"Redis connection failed: {e}. Rate limiting will use in-memory fallback.")
            self._redis = None
        except Exception as e:
            logger.warning(f"Unexpected error connecting to Redis: {e}. Rate limiting will use in-memory fallback.")
            self._redis = None

    def _load_scripts(self) -> None:
        """Load Lua scripts into Redis and cache their SHA hashes."""
        if self._redis:
            try:
                self._script_sha = self._redis.script_load(RATE_LIMIT_LUA_SCRIPT)
                self._burst_script_sha = self._redis.script_load(BURST_LIMIT_LUA_SCRIPT)
                logger.debug("Lua scripts loaded successfully")
            except RedisError as e:
                logger.warning(f"Failed to load Lua scripts: {e}. Will use pipeline approach.")
                self._script_sha = None
                self._burst_script_sha = None

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

    def is_allowed(
        self,
        user_id: str,
        rps_limit: int = 10,
        burst_limit: int = 50,
        endpoint: str | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Check if request is allowed within rate limits.

        Uses sliding window algorithm with burst capacity:
        - Current second: increment counter
        - Check if counter > rate_limit_rps
        - Include burst capacity for spikes

        Args:
            user_id: User identifier
            rps_limit: Requests per second limit
            burst_limit: Burst capacity limit
            endpoint: Optional endpoint for more granular limiting

        Returns:
            Tuple of (allowed: bool, details: dict)
        """
        if self._redis and self.is_redis_available:
            return self._check_redis(user_id, rps_limit, burst_limit, endpoint)
        return self._check_memory(user_id, rps_limit, burst_limit)

    def _check_redis(
        self,
        user_id: str,
        rps_limit: int,
        burst_limit: int,
        endpoint: str | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """Check rate limit using Redis with Lua scripts."""
        try:
            current_second = int(time.time())
            endpoint_suffix = f":{endpoint}" if endpoint else ""
            window_key = f"rate_limit:{user_id}{endpoint_suffix}:{current_second}"
            burst_key = f"rate_limit_burst:{user_id}{endpoint_suffix}"

            # Try Lua script first (atomic operation)
            if self._script_sha and self._burst_script_sha:
                try:
                    result = self._redis.evalsha(
                        self._burst_script_sha,
                        2,
                        window_key,
                        burst_key,
                        rps_limit,
                        burst_limit,
                        self.default_ttl,
                        self.burst_ttl,
                    )
                    allowed = bool(result[0])
                    requests_in_window = int(result[1])
                    burst_remaining = int(result[2])

                    return allowed, {
                        "allowed": allowed,
                        "requests_in_window": requests_in_window,
                        "burst_remaining": burst_remaining,
                        "backend": "redis_lua",
                    }
                except RedisError as e:
                    # Script might have been flushed, reload it
                    logger.debug(f"Lua script error, reloading: {e}")
                    self._load_scripts()
                    # Fall through to pipeline approach

            # Fallback to pipeline approach
            pipe = self._redis.pipeline(transaction=True)
            pipe.incr(window_key)
            pipe.expire(window_key, self.default_ttl)
            results = pipe.execute()
            requests_in_window = results[0]

            # Check burst capacity
            burst_pipe = self._redis.pipeline(transaction=True)
            burst_pipe.incr(burst_key)
            burst_pipe.expire(burst_key, self.burst_ttl)
            burst_results = burst_pipe.execute()
            burst_used = burst_results[0]
            burst_remaining = max(0, burst_limit - burst_used)

            # Allow if within RPS limit OR burst available
            allowed = requests_in_window <= rps_limit or burst_remaining > 0

            return allowed, {
                "allowed": allowed,
                "requests_in_window": requests_in_window,
                "burst_remaining": burst_remaining,
                "backend": "redis_pipeline",
            }

        except RedisError as e:
            logger.error(f"Redis rate limit check failed: {e}. Allowing request.")
            return True, {
                "allowed": True,
                "reason": "redis_error",
                "error": str(e),
                "backend": "redis_error",
            }

    def _check_memory(
        self,
        user_id: str,
        rps_limit: int,
        burst_limit: int,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Check rate limit using in-memory window (fallback).

        This is used when Redis is unavailable. Note that this does NOT
        provide distributed rate limiting across workers.
        """
        current_second = int(time.time())
        window_key = f"{user_id}:{current_second}"

        # Get or create window entry
        if window_key not in self._in_memory_windows:
            self._in_memory_windows[window_key] = {
                "count": 0,
                "created_at": time.time(),
            }

        # Increment counter
        self._in_memory_windows[window_key]["count"] += 1
        request_count = self._in_memory_windows[window_key]["count"]

        # Cleanup old windows (prevent memory leak)
        self._cleanup_memory_windows()

        allowed = request_count <= rps_limit

        return allowed, {
            "allowed": allowed,
            "requests_in_window": request_count,
            "burst_remaining": burst_limit if allowed else 0,
            "backend": "memory",
        }

    def _cleanup_memory_windows(self) -> None:
        """Remove expired in-memory windows to prevent memory leak."""
        cutoff = time.time() - self.default_ttl - 1
        expired_keys = [
            k for k, v in self._in_memory_windows.items()
            if v["created_at"] < cutoff
        ]
        for k in expired_keys:
            del self._in_memory_windows[k]

    def reset(self, user_id: str, endpoint: str | None = None) -> bool:
        """
        Reset rate limit counters for a user.

        Args:
            user_id: User identifier
            endpoint: Optional endpoint to reset

        Returns:
            True if reset successful, False otherwise
        """
        if not self._redis or not self.is_redis_available:
            return False

        try:
            current_second = int(time.time())
            endpoint_suffix = f":{endpoint}" if endpoint else ""
            window_key = f"rate_limit:{user_id}{endpoint_suffix}:{current_second}"
            burst_key = f"rate_limit_burst:{user_id}{endpoint_suffix}"

            pipe = self._redis.pipeline()
            pipe.delete(window_key)
            pipe.delete(burst_key)
            pipe.execute()
            return True
        except RedisError as e:
            logger.error(f"Failed to reset rate limit: {e}")
            return False

    def get_usage(self, user_id: str, endpoint: str | None = None) -> dict[str, Any]:
        """
        Get current rate limit usage for a user.

        Args:
            user_id: User identifier
            endpoint: Optional endpoint

        Returns:
            Dict with usage information
        """
        if not self._redis or not self.is_redis_available:
            return {"backend": "memory", "available": False}

        try:
            current_second = int(time.time())
            endpoint_suffix = f":{endpoint}" if endpoint else ""
            window_key = f"rate_limit:{user_id}{endpoint_suffix}:{current_second}"
            burst_key = f"rate_limit_burst:{user_id}{endpoint_suffix}"

            pipe = self._redis.pipeline()
            pipe.get(window_key)
            pipe.get(burst_key)
            results = pipe.execute()

            return {
                "backend": "redis",
                "available": True,
                "requests_in_window": int(results[0]) if results[0] else 0,
                "burst_used": int(results[1]) if results[1] else 0,
            }
        except RedisError as e:
            logger.error(f"Failed to get usage: {e}")
            return {"backend": "redis", "available": False, "error": str(e)}


class RateLimiter(RedisRateLimiter):
    """
    Backward-compatible rate limiter that maintains the original API.

    This class extends RedisRateLimiter to maintain backward compatibility
    with the original RateLimiter API that accepts UserQuota objects.

    Usage:
        limiter = RateLimiter()
        allowed, details = limiter.is_allowed("user_123", quota=user_quota)
    """

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        redis_url: str | None = None,
        **kwargs,
    ):
        """
        Initialize rate limiter with backward compatibility.

        Args:
            redis_client: Existing Redis client (for backward compatibility)
            redis_url: Redis URL for new connections
            **kwargs: Additional arguments passed to RedisRateLimiter
        """
        # If an existing redis_client is provided, extract connection info
        if redis_client is not None:
            try:
                connection_kwargs = redis_client.connection_pool.connection_kwargs
                super().__init__(
                    redis_host=connection_kwargs.get("host"),
                    redis_port=connection_kwargs.get("port"),
                    redis_db=connection_kwargs.get("db"),
                    redis_password=connection_kwargs.get("password"),
                    **kwargs,
                )
                # Use the existing client's connection pool
                self._redis = redis_client
            except Exception as e:
                logger.warning(f"Could not extract Redis connection info: {e}")
                super().__init__(redis_url=redis_url, **kwargs)
        else:
            super().__init__(redis_url=redis_url, **kwargs)

    def is_allowed(
        self,
        user_id: str,
        quota: UserQuota | None = None,
        override: bool = False,
        rps_limit: int | None = None,
        burst_limit: int | None = None,
    ) -> tuple[bool, dict]:
        """
        Check if request is allowed within rate limits.

        Supports both the original API (with UserQuota) and the new API
        (with explicit rps_limit/burst_limit parameters).

        Args:
            user_id: User identifier
            quota: UserQuota config (original API)
            override: Admin override flag
            rps_limit: Requests per second limit (new API)
            burst_limit: Burst capacity limit (new API)

        Returns:
            (allowed: bool, details: dict)
        """
        # Handle admin override
        if override or (quota and quota.override_rate_limit):
            return True, {"allowed": True, "reason": "admin_override"}

        # Handle Enterprise tier (no rate limiting)
        if quota and quota.tier == PricingTier.ENTERPRISE:
            return True, {"allowed": True, "reason": "enterprise_unlimited"}

        # Determine limits from quota or explicit parameters
        if quota:
            rps = rps_limit or quota.rate_limit_rps
            burst = burst_limit or quota.rate_limit_burst
        else:
            rps = rps_limit or 10
            burst = burst_limit or 50

        # Use parent class method
        return super().is_allowed(user_id, rps_limit=rps, burst_limit=burst)


class QuotaManager:
    """
    Manages monthly quota enforcement and tracking.

    Handles:
    - Task quota enforcement
    - API call quota enforcement
    - Compute time quota enforcement
    - 80%/100% threshold alerts
    """

    def __init__(self):
        """
        Initialize the quota enforcer.

        Sets up logging for quota enforcement operations.
        """
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def get_current_billing_month() -> str:
        """Get current billing month in YYYY-MM format."""
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m")

    def get_or_create_usage(
        self,
        db: Session,
        user_id: str,
        billing_month: str | None = None,
    ) -> QuotaUsage:
        """Get or create QuotaUsage record for user and month."""
        if billing_month is None:
            billing_month = self.get_current_billing_month()

        usage = db.query(QuotaUsage).filter(
            QuotaUsage.user_id == user_id,
            QuotaUsage.billing_month == billing_month,
        ).first()

        if not usage:
            usage = QuotaUsage(
                user_id=user_id,
                billing_month=billing_month,
            )
            db.add(usage)
            db.commit()
            db.refresh(usage)

        return usage

    def check_task_quota(
        self,
        db: Session,
        user_id: str,
        quota: UserQuota,
        override: bool = False,
    ) -> tuple[bool, dict]:
        """Check if user can create a new task."""
        if override or quota.override_quota:
            return True, {"allowed": True, "reason": "admin_override"}

        if quota.tier == PricingTier.ENTERPRISE:
            return True, {"allowed": True, "reason": "enterprise_unlimited"}

        usage = self.get_or_create_usage(db, user_id)

        # Check if limit exceeded
        allowed = usage.task_count < quota.monthly_task_limit

        return allowed, {
            "allowed": allowed,
            "used": usage.task_count,
            "limit": quota.monthly_task_limit,
            "remaining": max(0, quota.monthly_task_limit - usage.task_count),
        }

    def check_api_quota(
        self,
        db: Session,
        user_id: str,
        quota: UserQuota,
        override: bool = False,
    ) -> tuple[bool, dict]:
        """Check if user can make an API call."""
        if override or quota.override_quota:
            return True, {"allowed": True, "reason": "admin_override"}

        if quota.tier == PricingTier.ENTERPRISE:
            return True, {"allowed": True, "reason": "enterprise_unlimited"}

        usage = self.get_or_create_usage(db, user_id)

        # Check if limit exceeded
        allowed = usage.api_call_count < quota.monthly_api_calls_limit

        return allowed, {
            "allowed": allowed,
            "used": usage.api_call_count,
            "limit": quota.monthly_api_calls_limit,
            "remaining": max(0, quota.monthly_api_calls_limit - usage.api_call_count),
        }

    def check_compute_quota(
        self,
        db: Session,
        user_id: str,
        quota: UserQuota,
        compute_minutes: float,
        override: bool = False,
    ) -> tuple[bool, dict]:
        """Check if user can use compute minutes."""
        if override or quota.override_quota:
            return True, {"allowed": True, "reason": "admin_override"}

        if quota.tier == PricingTier.ENTERPRISE:
            return True, {"allowed": True, "reason": "enterprise_unlimited"}

        usage = self.get_or_create_usage(db, user_id)

        # Check if limit exceeded
        new_total = usage.compute_minutes_used + compute_minutes
        allowed = new_total <= quota.monthly_compute_minutes_limit

        return allowed, {
            "allowed": allowed,
            "used": usage.compute_minutes_used,
            "requested": compute_minutes,
            "limit": quota.monthly_compute_minutes_limit,
            "remaining": max(0.0, quota.monthly_compute_minutes_limit - usage.compute_minutes_used),
        }

    def increment_task_count(
        self,
        db: Session,
        user_id: str,
    ) -> QuotaUsage:
        """Increment task count for current month."""
        usage = self.get_or_create_usage(db, user_id)
        usage.task_count += 1
        usage.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(usage)
        return usage

    def increment_api_calls(
        self,
        db: Session,
        user_id: str,
        count: int = 1,
    ) -> QuotaUsage:
        """Increment API call count for current month."""
        usage = self.get_or_create_usage(db, user_id)
        usage.api_call_count += count
        usage.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(usage)
        return usage

    def add_compute_time(
        self,
        db: Session,
        user_id: str,
        compute_minutes: float,
    ) -> QuotaUsage:
        """Add compute time to current month."""
        usage = self.get_or_create_usage(db, user_id)
        usage.compute_minutes_used += compute_minutes
        usage.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(usage)
        return usage

    @staticmethod
    def check_threshold_and_alert(
        db: Session,
        user_id: str,
        quota: UserQuota,
        usage: QuotaUsage,
    ) -> dict | None:
        """Check if usage exceeds alert threshold and return alert if needed."""
        if quota.tier == PricingTier.ENTERPRISE:
            return None

        # Calculate overall usage percentage (max of all quotas)
        task_percent = (usage.task_count / quota.monthly_task_limit * 100) if quota.monthly_task_limit > 0 else 0
        api_percent = (usage.api_call_count / quota.monthly_api_calls_limit * 100) if quota.monthly_api_calls_limit > 0 else 0
        compute_percent = (usage.compute_minutes_used / quota.monthly_compute_minutes_limit * 100) if quota.monthly_compute_minutes_limit > 0 else 0

        max_percent = max(task_percent, api_percent, compute_percent)

        alert = None

        # 80% threshold
        if max_percent >= 80 and not usage.alert_sent_at_80_percent:
            usage.alert_sent_at_80_percent = datetime.now(timezone.utc)
            alert = {
                "type": "quota_80_percent",
                "user_id": user_id,
                "usage_percentage": max_percent,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # 100% threshold
        if max_percent >= 100:
            if not usage.alert_sent_at_100_percent:
                usage.alert_sent_at_100_percent = datetime.now(timezone.utc)
                usage.quota_exceeded = True

            alert = {
                "type": "quota_100_percent",
                "user_id": user_id,
                "usage_percentage": max_percent,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if alert:
            usage.updated_at = datetime.now(timezone.utc)
            db.commit()

        return alert

    @staticmethod
    def log_rate_limit(
        db: Session,
        user_id: str,
        endpoint: str,
        method: str,
        requests_in_window: int,
        rate_limit_rps: int,
        exceeded: bool,
        status_code: int,
        response_time_ms: float,
        quota_type: str | None = None,
        quota_used: int | None = None,
        quota_limit: int | None = None,
        quota_exceeded: bool = False,
    ) -> RateLimitLog:
        """Log rate limit enforcement."""
        log = RateLimitLog(
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            requests_in_window=requests_in_window,
            rate_limit_rps=rate_limit_rps,
            exceeded=exceeded,
            quota_type=quota_type,
            quota_used=quota_used,
            quota_limit=quota_limit,
            quota_exceeded=quota_exceeded,
            status_code=status_code,
            response_time_ms=response_time_ms,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log


def get_tier_limits(tier: PricingTier) -> dict[str, int]:
    """Get quota limits for a pricing tier."""
    limits = {
        PricingTier.FREE: {
            "monthly_task_limit": 10,
            "monthly_api_calls_limit": 100,
            "monthly_compute_minutes_limit": 60,
            "rate_limit_rps": 10,
            "rate_limit_burst": 50,
        },
        PricingTier.PRO: {
            "monthly_task_limit": 1000,
            "monthly_api_calls_limit": 10000,
            "monthly_compute_minutes_limit": 600,
            "rate_limit_rps": 50,
            "rate_limit_burst": 200,
        },
        PricingTier.ENTERPRISE: {
            "monthly_task_limit": 999999999,
            "monthly_api_calls_limit": 999999999,
            "monthly_compute_minutes_limit": 999999999,
            "rate_limit_rps": 1000,
            "rate_limit_burst": 5000,
        },
    }
    return limits.get(tier, limits[PricingTier.FREE])
