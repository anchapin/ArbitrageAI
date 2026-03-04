"""
File and delivery endpoints module.

This module contains file upload validation, delivery endpoints,
and rate limiting for secure file delivery.

Rate Limiting:
- Uses Redis-based distributed rate limiting (QAQC-009)
- Falls back to in-memory limiting when Redis unavailable
- Supports both task-based and IP-based rate limiting
"""

from datetime import datetime, timedelta, timezone
import os
import re
import time as _time
from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Delivery token TTL in hours (configurable via env)
from src.config.config_manager import ConfigManager  # noqa: E402

DELIVERY_TOKEN_TTL_HOURS = ConfigManager.get("DELIVERY_TOKEN_TTL_HOURS")

# Rate limiting: max failed delivery attempts per task before lockout
DELIVERY_MAX_FAILED_ATTEMPTS = ConfigManager.get("DELIVERY_MAX_FAILED_ATTEMPTS")
DELIVERY_LOCKOUT_SECONDS = ConfigManager.get("DELIVERY_LOCKOUT_SECONDS")

# IP-based rate limiting
DELIVERY_MAX_ATTEMPTS_PER_IP = ConfigManager.get("DELIVERY_MAX_ATTEMPTS_PER_IP")
DELIVERY_IP_LOCKOUT_SECONDS = ConfigManager.get("DELIVERY_IP_LOCKOUT_SECONDS")

# In-memory rate limiter for backward compatibility with tests
# In production, Redis is used instead (QAQC-009)
_delivery_rate_limits: dict[str, tuple[int, float]] = {}
_delivery_ip_rate_limits: dict[str, tuple[int, float]] = {}

# Redis rate limiter instance (lazy-loaded)
_redis_rate_limiter = None


def _get_redis_rate_limiter():
    """Get or create Redis rate limiter instance."""
    global _redis_rate_limiter
    if _redis_rate_limiter is None:
        # Check if rate limiting should be disabled (for tests)
        if os.getenv("DISABLE_RATE_LIMITING") == "true":
            return None
        
        try:
            from src.utils.redis_rate_limiter import RedisRateLimiter
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            _redis_rate_limiter = RedisRateLimiter(redis_url=redis_url, key_prefix="delivery")
            return _redis_rate_limiter
        except ImportError:
            logger.warning("Redis rate limiter module not available, using in-memory")
            return None
        except Exception as e:
            logger.warning(f"Redis rate limiter initialization failed: {e}, using in-memory")
            return None
    return _redis_rate_limiter


class DeliveryTokenRequest(BaseModel):
    """Validated request model for delivery endpoint."""
    task_id: str = Field(..., min_length=1, max_length=64, description="Task ID")
    token: str = Field(..., min_length=20, max_length=256, description="Delivery token")

    @field_validator("task_id", mode="before")
    @classmethod
    def validate_task_id(cls, v: Any) -> Any:
        """Sanitize task_id - allow UUID format only."""
        if not isinstance(v, str):
            return v
        v = v.lower().strip()
        if not re.match(r"^[a-f0-9\-]{36}$", v):
            raise ValueError("Invalid task_id format (must be UUID)")
        return v

    @field_validator("token", mode="before")
    @classmethod
    def validate_token(cls, v: Any) -> Any:
        """Sanitize token - alphanumeric, hyphens, underscores only."""
        if not isinstance(v, str):
            return v
        v = v.strip()
        if not re.match(r"^[a-zA-Z0-9\-_]+$", v):
            raise ValueError("Invalid token format (contains invalid characters)")
        return v


class DeliveryResponse(BaseModel):
    """Validated response model for delivery endpoint."""
    task_id: str
    title: str
    domain: str
    result_type: str
    result_url: str | None = None
    result_image_url: str | None = None
    result_document_url: str | None = None
    result_spreadsheet_url: str | None = None
    delivered_at: str


class AddressValidationModel(BaseModel):
    """Validation model for delivery addresses."""
    address: str
    city: str
    postal_code: str
    country: str

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9\s,.-]+$", v):
            raise ValueError("Contains invalid characters")
        return v

    @field_validator("city", "country")
    @classmethod
    def validate_no_numbers(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z\s,.-]+$", v):
            raise ValueError("Contains invalid characters or numbers")
        return v

    @field_validator("country")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        if len(v) != 2 or not v.isalpha():
            raise ValueError("Must be a 2-letter ISO country code")
        return v.upper()


class DeliveryAmountModel(BaseModel):
    """Validation model for delivery amounts."""
    amount_cents: int
    currency: str = "USD"

    @field_validator("amount_cents")
    @classmethod
    def validate_positive_amount(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Amount must be positive")
        max_amount = ConfigManager.get("MAX_DELIVERY_AMOUNT_CENTS")
        if v > max_amount:
            raise ValueError(f"Amount exceeds maximum allowed ({max_amount})")
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if v.upper() not in {"USD", "EUR", "GBP"}:
            raise ValueError("Unsupported currency")
        return v.upper()


class DeliveryTimestampModel(BaseModel):
    """Validation model for delivery timestamps."""
    created_at: datetime
    expires_at: datetime

    @field_validator("created_at")
    @classmethod
    def validate_not_future(cls, v: datetime) -> datetime:
        if v > datetime.now(v.tzinfo or timezone.utc):
            raise ValueError("Created at cannot be in the future")
        return v

    @field_validator("expires_at")
    @classmethod
    def validate_not_past(cls, v: datetime, info: ValidationInfo) -> datetime:
        if v < datetime.now(v.tzinfo or timezone.utc):
            raise ValueError("Expires at cannot be in the past")
        created_at = info.data.get("created_at")
        if created_at and v <= created_at:
            raise ValueError("Expires at must be after created at")
        max_days = ConfigManager.get("MAX_DELIVERY_TOKEN_TTL_DAYS")
        if v > datetime.now(timezone.utc) + timedelta(days=max_days):
            raise ValueError(f"Expires at too far in future (max {max_days} days)")
        return v


def _check_delivery_rate_limit(task_id: str) -> bool:
    """
    Check if a task_id is rate-limited for delivery attempts.
    
    Uses Redis for distributed rate limiting (QAQC-009).
    Falls back to in-memory limiting when Redis unavailable.
    
    Returns True if the request is allowed, False if rate-limited.
    """
    # Try Redis first
    limiter = _get_redis_rate_limiter()
    if limiter:
        try:
            allowed, _ = limiter.check_rate_limit(
                key=f"task:{task_id}",
                max_requests=DELIVERY_MAX_FAILED_ATTEMPTS,
                window_seconds=DELIVERY_LOCKOUT_SECONDS,
                algorithm="sliding",
            )
            return allowed
        except Exception as e:
            logger.warning(f"Redis rate limit check failed: {e}, using in-memory fallback")
    
    # Fallback to in-memory (for tests or when Redis unavailable)
    entry = _delivery_rate_limits.get(task_id)
    if entry is None:
        return True
    fail_count, first_fail_ts = entry
    if _time.time() - first_fail_ts > DELIVERY_LOCKOUT_SECONDS:
        del _delivery_rate_limits[task_id]
        return True
    return fail_count < DELIVERY_MAX_FAILED_ATTEMPTS


def _record_delivery_failure(task_id: str, ip: str | None = None) -> None:
    """
    Record a failed delivery attempt for rate limiting.
    
    Uses Redis for distributed tracking (QAQC-009).
    Also updates in-memory dict for backward compatibility.
    """
    # Record in Redis
    limiter = _get_redis_rate_limiter()
    if limiter:
        try:
            limiter.record_event(f"task:{task_id}", "failure")
            if ip:
                limiter.record_event(f"ip:{ip}", "failure")
        except Exception as e:
            logger.warning(f"Failed to record delivery failure in Redis: {e}")
    
    # Also update in-memory for backward compatibility
    entry = _delivery_rate_limits.get(task_id)
    if entry is None:
        _delivery_rate_limits[task_id] = (1, _time.time())
    else:
        fail_count, first_fail_ts = entry
        _delivery_rate_limits[task_id] = (fail_count + 1, first_fail_ts)


def _check_delivery_ip_rate_limit(ip: str) -> bool:
    """
    Check if an IP is rate-limited for delivery attempts.
    
    Uses Redis for distributed rate limiting (QAQC-009).
    Falls back to in-memory limiting when Redis unavailable.
    
    Returns True if the request is allowed, False if rate-limited.
    """
    # Try Redis first
    limiter = _get_redis_rate_limiter()
    if limiter:
        try:
            allowed, _ = limiter.check_rate_limit(
                key=f"ip:{ip}",
                max_requests=DELIVERY_MAX_ATTEMPTS_PER_IP,
                window_seconds=DELIVERY_IP_LOCKOUT_SECONDS,
                algorithm="sliding",
            )
            return allowed
        except Exception as e:
            logger.warning(f"Redis IP rate limit check failed: {e}, using in-memory fallback")
    
    # Fallback to in-memory
    entry = _delivery_ip_rate_limits.get(ip)
    if entry is None:
        return True
    attempt_count, first_attempt_ts = entry
    if _time.time() - first_attempt_ts > DELIVERY_IP_LOCKOUT_SECONDS:
        del _delivery_ip_rate_limits[ip]
        return True
    return attempt_count < DELIVERY_MAX_ATTEMPTS_PER_IP


def _record_ip_delivery_attempt(ip: str) -> None:
    """
    Record a delivery attempt from an IP.
    
    Uses Redis for distributed tracking (QAQC-009).
    Also updates in-memory dict for backward compatibility.
    """
    # Record in Redis
    limiter = _get_redis_rate_limiter()
    if limiter:
        try:
            limiter.record_event(f"ip:{ip}", "attempt")
        except Exception as e:
            logger.warning(f"Failed to record IP attempt in Redis: {e}")
    
    # Also update in-memory for backward compatibility
    entry = _delivery_ip_rate_limits.get(ip)
    if entry is None:
        _delivery_ip_rate_limits[ip] = (1, _time.time())
    else:
        attempt_count, first_attempt_ts = entry
        _delivery_ip_rate_limits[ip] = (attempt_count + 1, first_attempt_ts)


def _sanitize_string(value: str, max_length: int = 500) -> str:
    """Sanitize string input to prevent injection attacks."""
    if not isinstance(value, str):
        return value
    sanitized = value.replace("\x00", "")
    return sanitized[:max_length].strip()


# Export rate limit dicts for testing
__all__ = [
    "AddressValidationModel",
    "DeliveryAmountModel",
    "DeliveryResponse",
    "DeliveryTimestampModel",
    "DeliveryTokenRequest",
    "_check_delivery_ip_rate_limit",
    "_check_delivery_rate_limit",
    "_delivery_ip_rate_limits",
    "_delivery_rate_limits",
    "_record_delivery_failure",
    "_record_ip_delivery_attempt",
    "_sanitize_string",
]
