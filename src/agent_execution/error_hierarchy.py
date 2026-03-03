"""Error hierarchy for smart retry logic - Issue #37"""


class CustomError(Exception):
    """Base exception for all custom errors"""


class RetryableError(CustomError):
    """Error that can be safely retried"""


class PermanentError(CustomError):
    """Error that should not be retried"""


class NetworkError(RetryableError):
    """Network-related errors (transient)"""


class RateLimitError(RetryableError):
    """Rate limit hit (transient, can retry after backoff)"""


class ValidationError(PermanentError):
    """Input validation failed (permanent)"""


class AuthenticationError(PermanentError):
    """Authentication failed (permanent)"""
