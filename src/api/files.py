"""
File and delivery endpoints module.

This module contains file upload validation, delivery endpoints,
and rate limiting for secure file delivery.
"""

import re
import secrets
import time as _time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Header, HTTPException, Request
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from sqlalchemy.orm import Session

from .models import Task, TaskStatus
from .database import get_db
from src.utils.file_validator import validate_file_upload
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Delivery token TTL in hours (configurable via env)
from src.config.config_manager import ConfigManager
DELIVERY_TOKEN_TTL_HOURS = ConfigManager.get("DELIVERY_TOKEN_TTL_HOURS")

# Rate limiting: max failed delivery attempts per task before lockout
DELIVERY_MAX_FAILED_ATTEMPTS = ConfigManager.get("DELIVERY_MAX_FAILED_ATTEMPTS")
DELIVERY_LOCKOUT_SECONDS = ConfigManager.get("DELIVERY_LOCKOUT_SECONDS")

# IP-based rate limiting
DELIVERY_MAX_ATTEMPTS_PER_IP = ConfigManager.get("DELIVERY_MAX_ATTEMPTS_PER_IP")
DELIVERY_IP_LOCKOUT_SECONDS = ConfigManager.get("DELIVERY_IP_LOCKOUT_SECONDS")

# In-memory rate limiter: { task_id: (fail_count, first_fail_timestamp) }
_delivery_rate_limits: dict[str, tuple[int, float]] = {}

# IP-level rate limiter: { ip: (attempt_count, first_attempt_timestamp) }
_delivery_ip_rate_limits: dict[str, tuple[int, float]] = {}


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
    """Check if a task_id is rate-limited for delivery attempts."""
    entry = _delivery_rate_limits.get(task_id)
    if entry is None:
        return True
    fail_count, first_fail_ts = entry
    if _time.time() - first_fail_ts > DELIVERY_LOCKOUT_SECONDS:
        del _delivery_rate_limits[task_id]
        return True
    return fail_count < DELIVERY_MAX_FAILED_ATTEMPTS


def _record_delivery_failure(task_id: str, ip: str | None = None) -> None:
    """Record a failed delivery attempt for rate limiting."""
    entry = _delivery_rate_limits.get(task_id)
    if entry is None:
        _delivery_rate_limits[task_id] = (1, _time.time())
    else:
        fail_count, first_fail_ts = entry
        _delivery_rate_limits[task_id] = (fail_count + 1, first_fail_ts)


def _check_delivery_ip_rate_limit(ip: str) -> bool:
    """Check if an IP is rate-limited for delivery attempts."""
    entry = _delivery_ip_rate_limits.get(ip)
    if entry is None:
        return True
    attempt_count, first_attempt_ts = entry
    if _time.time() - first_attempt_ts > DELIVERY_IP_LOCKOUT_SECONDS:
        del _delivery_ip_rate_limits[ip]
        return True
    return attempt_count < DELIVERY_MAX_ATTEMPTS_PER_IP


def _record_ip_delivery_attempt(ip: str) -> None:
    """Record a delivery attempt from an IP."""
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
    "DeliveryTokenRequest",
    "DeliveryResponse",
    "AddressValidationModel",
    "DeliveryAmountModel",
    "DeliveryTimestampModel",
    "_delivery_rate_limits",
    "_delivery_ip_rate_limits",
    "_check_delivery_rate_limit",
    "_record_delivery_failure",
    "_check_delivery_ip_rate_limit",
    "_record_ip_delivery_attempt",
    "_sanitize_string",
]
