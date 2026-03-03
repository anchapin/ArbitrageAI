---
created: 2026-03-03
priority: MEDIUM
qaqc_section: 5.1
estimated_effort: 3 days
target_milestone: Phase 4 - Week 7-8
---

# [PERFORMANCE] Replace In-Memory Rate Limiting with Redis

## ⚡ Performance Issue - Distributed Rate Limiting

**Priority:** MEDIUM  
**Labels:** performance, redis, rate-limiting, qaqc-review, distributed-systems  
**QA/QC Review Reference:** Section 5.1 - In-Memory Rate Limiting

---

## 📍 Location

- **Files:**
  - `src/api/main.py` (lines ~250-280) - In-memory rate limit dicts
  - `src/api/rate_limiter.py` - Redis rate limiter (already exists!)
  - `src/api/rate_limit_middleware.py` - Middleware using in-memory
- **Component:** API Rate Limiting
- **Environment:** Production (multi-worker deployments)

---

## 🐛 Issue Description

The application uses **in-memory dictionaries** for rate limiting in production:

```python
# src/api/main.py (lines ~250-280)
# In-memory rate limiter: { task_id: (fail_count, first_fail_timestamp) }
_delivery_rate_limits: dict[str, tuple[int, float]] = {}

# IP-level rate limiter: { ip: (attempt_count, first_attempt_timestamp) }
_delivery_ip_rate_limits: dict[str, tuple[int, float]] = {}
```

**Problems:**
1. **Multi-Worker Ineffective:** Each worker has separate counters
2. **Memory Leaks:** Dicts grow indefinitely
3. **No Persistence:** Rate limits reset on restart
4. **Race Conditions:** Concurrent requests not properly counted
5. **Scaling Issues:** Doesn't work with horizontal scaling

The codebase already has `RedisRateLimiter` in `src/api/rate_limiter.py` but it's not being used consistently!

---

## ⚠️ Risk Assessment

- **Severity:** Medium (security and reliability)
- **Impact:** Rate limits bypassed in production, DoS vulnerability
- **Likelihood:** High (will occur in any multi-worker deployment)
- **Performance:** Moderate (memory growth over time)

---

## 🎯 Acceptance Criteria

- [ ] All in-memory rate limiting replaced with Redis
- [ ] Rate limits work correctly across multiple workers
- [ ] Memory usage stable over time
- [ ] Rate limit tests passing
- [ ] Load tests show correct behavior
- [ ] Documentation updated

---

## 🔧 Implementation Notes

### Current State Analysis

**In-Memory Implementation (main.py):**
```python
# Current problematic implementation
_delivery_rate_limits: dict[str, tuple[int, float]] = {}

def _check_delivery_rate_limit(task_id: str) -> bool:
    """Check if task_id is rate-limited."""
    entry = _delivery_rate_limits.get(task_id)
    if entry is None:
        return True
    
    fail_count, first_fail_ts = entry
    if _time.time() - first_fail_ts > DELIVERY_LOCKOUT_SECONDS:
        del _delivery_rate_limits[task_id]
        return True
    
    return fail_count < DELIVERY_MAX_FAILED_ATTEMPTS
```

**Existing Redis Implementation (rate_limiter.py):**
```python
# Already implemented but not used!
class RateLimiter:
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        if redis_client is None:
            redis_client = redis.Redis(
                host="localhost", port=6379, db=0, decode_responses=True
            )
        self.redis = redis_client
    
    def is_allowed(self, user_id: str, quota: UserQuota) -> Tuple[bool, Dict]:
        """Check if request allowed using Redis sliding window."""
        # ... implementation exists
```

### Solution: Use Existing Redis Rate Limiter

#### Step 1: Create Unified Rate Limiter Service

```python
# src/api/rate_limit_service.py
"""Unified rate limiting service using Redis."""

import time
import redis
from typing import Optional, Tuple, Dict
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class RedisRateLimiter:
    """
    Redis-backed rate limiter for distributed systems.
    
    Uses sliding window algorithm with atomic operations.
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """Initialize Redis connection."""
        redis_url = redis_url or "redis://localhost:6379/0"
        
        try:
            self.redis = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            self.redis.ping()
            logger.info("✅ Redis rate limiter connected")
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory fallback: {e}")
            self.redis = None
            self._memory_store = {}
    
    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> Tuple[bool, Dict]:
        """
        Check if request is within rate limit.
        
        Args:
            key: Unique identifier (e.g., "delivery:task_id:123")
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
            
        Returns:
            (allowed: bool, info: dict)
        """
        if self.redis is None:
            return self._check_memory(key, max_requests, window_seconds)
        
        try:
            current_time = int(time.time())
            window_key = f"ratelimit:{key}:{current_time // window_seconds}"
            
            # Atomic increment
            current_count = self.redis.incr(window_key)
            
            # Set expiry on first request
            if current_count == 1:
                self.redis.expire(window_key, window_seconds * 2)
            
            allowed = current_count <= max_requests
            
            return allowed, {
                "allowed": allowed,
                "current_count": current_count,
                "max_requests": max_requests,
                "window_seconds": window_seconds,
                "retry_after": window_seconds if not allowed else 0,
            }
        
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            # Fallback to allow request
            return True, {"error": str(e), "fallback": True}
    
    def _check_memory(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> Tuple[bool, Dict]:
        """In-memory fallback (development only)."""
        current_time = time.time()
        window_key = f"{key}:{int(current_time // window_seconds)}"
        
        if window_key not in self._memory_store:
            self._memory_store = {
                k: v for k, v in self._memory_store.items()
                if int(current_time // window_seconds) - int(v[1] // window_seconds) < 2
            }
        
        entry = self._memory_store.get(window_key, (0, current_time))
        current_count = entry[0] + 1
        self._memory_store[window_key] = (current_count, current_time)
        
        allowed = current_count <= max_requests
        
        return allowed, {
            "allowed": allowed,
            "current_count": current_count,
            "fallback": True,
        }


# Global instance
_rate_limiter: Optional[RedisRateLimiter] = None


def get_rate_limiter() -> RedisRateLimiter:
    """Get or create rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        from src.config import get_redis_url
        _rate_limiter = RedisRateLimiter(get_redis_url())
    return _rate_limiter


def rate_limit(
    key_func,
    max_requests: int,
    window_seconds: int,
):
    """
    Decorator for rate limiting endpoints.
    
    Args:
        key_func: Function to extract rate limit key from request
        max_requests: Maximum requests allowed
        window_seconds: Time window
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from fastapi import HTTPException, Request
            
            # Get request from args
            request = next((arg for arg in args if isinstance(arg, Request)), None)
            if not request:
                return await func(*args, **kwargs)
            
            key = key_func(request, *args, **kwargs)
            limiter = get_rate_limiter()
            
            allowed, info = limiter.check_rate_limit(
                key, max_requests, window_seconds
            )
            
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(info["retry_after"])},
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
```

#### Step 2: Update main.py to Use Redis Rate Limiter

```python
# src/api/main.py

# Remove these lines:
# _delivery_rate_limits: dict[str, tuple[int, float]] = {}
# _delivery_ip_rate_limits: dict[str, tuple[int, float]] = {}

# Add import:
from .rate_limit_service import get_rate_limiter

# Update rate limit functions:
def _check_delivery_rate_limit(task_id: str, client_ip: str = None) -> bool:
    """Check rate limit using Redis."""
    limiter = get_rate_limiter()
    
    # Check task-level limit
    task_key = f"delivery:task:{task_id}"
    allowed, _ = limiter.check_rate_limit(
        task_key,
        max_requests=DELIVERY_MAX_FAILED_ATTEMPTS,
        window_seconds=DELIVERY_LOCKOUT_SECONDS,
    )
    
    if not allowed:
        return False
    
    # Check IP-level limit if IP provided
    if client_ip:
        ip_key = f"delivery:ip:{client_ip}"
        allowed, _ = limiter.check_rate_limit(
            ip_key,
            max_requests=DELIVERY_MAX_ATTEMPTS_PER_IP,
            window_seconds=DELIVERY_IP_LOCKOUT_SECONDS,
        )
    
    return allowed


def _record_delivery_failure(task_id: str, ip: str = None) -> None:
    """Record delivery failure in Redis."""
    limiter = get_rate_limiter()
    
    # Increment task counter
    task_key = f"delivery:task:{task_id}"
    limiter.check_rate_limit(
        task_key,
        max_requests=DELIVERY_MAX_FAILED_ATTEMPTS,
        window_seconds=DELIVERY_LOCKOUT_SECONDS,
    )
    
    # Increment IP counter
    if ip:
        ip_key = f"delivery:ip:{ip}"
        limiter.check_rate_limit(
            ip_key,
            max_requests=DELIVERY_MAX_ATTEMPTS_PER_IP,
            window_seconds=DELIVERY_IP_LOCKOUT_SECONDS,
        )
```

#### Step 3: Add Rate Limit Headers

```python
# Add to rate_limit_service.py

def add_rate_limit_headers(response: Response, info: Dict) -> Response:
    """Add rate limit headers to response."""
    response.headers["X-RateLimit-Limit"] = str(info["max_requests"])
    response.headers["X-RateLimit-Remaining"] = str(
        max(0, info["max_requests"] - info["current_count"])
    )
    response.headers["X-RateLimit-Reset"] = str(
        int(time.time()) + info["window_seconds"]
    )
    
    if not info["allowed"]:
        response.headers["Retry-After"] = str(info["retry_after"])
    
    return response
```

---

## 📋 Testing Requirements

### Unit Tests:
```python
# tests/test_rate_limit_service.py

def test_redis_rate_limiter_allows_within_limit():
    """Test that requests within limit are allowed."""
    limiter = RedisRateLimiter(redis_url="redis://localhost:6379/0")
    
    for i in range(5):
        allowed, info = limiter.check_rate_limit(
            "test:user:1",
            max_requests=10,
            window_seconds=60,
        )
        assert allowed is True

def test_redis_rate_limiter_blocks_over_limit():
    """Test that requests over limit are blocked."""
    limiter = RedisRateLimiter(redis_url="redis://localhost:6379/0")
    
    # Make 10 requests
    for i in range(10):
        limiter.check_rate_limit(
            "test:user:2",
            max_requests=10,
            window_seconds=60,
        )
    
    # 11th request should be blocked
    allowed, info = limiter.check_rate_limit(
        "test:user:2",
        max_requests=10,
        window_seconds=60,
    )
    assert allowed is False
    assert info["retry_after"] > 0
```

### Integration Tests:
```python
# tests/test_rate_limiting_integration.py

async def test_delivery_endpoint_rate_limiting():
    """Test that delivery endpoint enforces rate limits."""
    client = TestClient(app)
    
    # Make requests up to limit
    for i in range(DELIVERY_MAX_FAILED_ATTEMPTS):
        response = client.post(
            f"/api/delivery/{task_id}",
            json={"token": "invalid"},
        )
        assert response.status_code != 429
    
    # Next request should be rate limited
    response = client.post(
        f"/api/delivery/{task_id}",
        json={"token": "invalid"},
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers
```

---

## 📚 References

- **QA/QC Review:** Deep QA/QC Review - March 2026, Section 5.1
- **Redis Documentation:** https://redis.io/
- **Rate Limiting Patterns:** https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting
- **Related Issues:** QAQC-011 (N+1 queries)

---

## 🎯 Success Metrics

- [ ] Zero in-memory rate limiting in production code
- [ ] Rate limits work across multiple workers
- [ ] Memory usage stable (<10MB growth over 24h)
- [ ] All rate limit tests passing
- [ ] Load test shows correct rate limiting

---

## 📝 Additional Notes

### Migration Plan:
1. Deploy `rate_limit_service.py` alongside existing code
2. Test with both in-memory and Redis
3. Switch to Redis-only
4. Remove in-memory fallback code
5. Monitor rate limiting metrics

### Monitoring:
```python
# Add metrics collection
from prometheus_client import Counter

rate_limit_hits = Counter('rate_limit_hits_total', 'Rate limit hits', ['endpoint'])
rate_limit_blocks = Counter('rate_limit_blocks_total', 'Rate limit blocks', ['endpoint'])
```

---

**Created from:** Deep QA/QC Review - March 3, 2026  
**Issue Template:** qaqc-performance.md
