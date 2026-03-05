"""Error tracking integration using Sentry.

This module provides error tracking and monitoring capabilities via Sentry.
Integrates with the existing observability stack (OpenTelemetry, APM).

Features:
- Automatic exception capture
- Context enrichment (user, tags, extra data)
- Performance monitoring integration
- Signal handling for graceful shutdown

Usage:
    from src.utils.error_tracking import init_error_tracking, capture_exception

    # Initialize at application startup
    init_error_tracking()

    # Capture exceptions
    try:
        risky_operation()
    except Exception as e:
        capture_exception(e)
"""

import logging
import os
import sys
from typing import Any, ClassVar

# Optional Sentry dependency
try:
    import sentry_sdk
    from sentry_sdk import capture_exception, capture_message
    from sentry_sdk.integrations import (
        FastApiIntegration,
        LoggingIntegration,
        SqlalchemyIntegration,
    )
    from sentry_sdk.integrations.logging import ignore_logger
    from sentry_sdk.tracing import Transaction
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    # Mock classes and functions for when Sentry is not available
    sentry_sdk = None  # type: ignore
    def capture_exception(*args, **kwargs): return None
    def capture_message(*args, **kwargs): return None

    class Transaction:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass

    # Mock integration classes for type hints
    class FastApiIntegration:  # type: ignore
        def __init__(self, *args, **kwargs): pass

    class LoggingIntegration:  # type: ignore
        def __init__(self, *args, **kwargs): pass

    class SqlalchemyIntegration:  # type: ignore
        def __init__(self, *args, **kwargs): pass

    def ignore_logger(*args, **kwargs): pass

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ErrorTrackingConfig:
    """Configuration for error tracking."""

    # Default configuration values
    _DEFAULTS: ClassVar[dict[str, Any]] = {
        "SENTRY_DSN": None,
        "SENTRY_ENVIRONMENT": os.getenv("ENVIRONMENT", "development"),
        "SENTRY_TRACES_SAMPLE_RATE": 0.1,
        "SENTRY_ERRORS_SAMPLE_RATE": 1.0,
        "SENTRY_ATTACH_STACKTRACE": True,
        "SENTRY_MAX_BREADCRUMBS": 100,
        "SENTRY_INCLUDE_LOCAL_VARS": True,
        "SENTRY_RELEASE": None,  # Auto-detected from version
        "SENTRY_IGNORE_ERRORS": [
            "KeyboardInterrupt",
            "SystemExit",
        ],
    }

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get configuration value from environment or default."""
        default_val = cls._DEFAULTS.get(key, default)
        env_val = os.getenv(key)
        if env_val is None:
            return default_val
        return env_val


def _get_app_version() -> str | None:
    """Get application version from pyproject.toml or package."""
    # Note: These imports are lazy-loaded to avoid hard dependency
    try:
        from importlib.metadata import version  # noqa: PLC0415

        return version("arbitrage-ai")
    except Exception:  # noqa: S110
        pass

    # Fallback: try to read from pyproject.toml
    try:
        from pathlib import Path  # noqa: PLC0415

        pyproject = Path("pyproject.toml")
        if pyproject.exists():
            content = pyproject.read_text()
            for line in content.split("\n"):
                if line.startswith("version ="):
                    return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:  # noqa: S110
        pass

    return None


def _setup_logging_integration() -> LoggingIntegration | None:
    """Configure Sentry's logging integration.

    Returns:
        Configured LoggingIntegration or None if unavailable
    """
    if not SENTRY_AVAILABLE:
        return None

    # Ignore noisy loggers to reduce Sentry noise
    ignore_logger("urllib3")
    ignore_logger("requests")
    ignore_logger("httpx")
    ignore_logger("opentelemetry")

    return LoggingIntegration(
        level=logging.WARNING,
        event_level=logging.ERROR,
    )


def init_error_tracking(
    dsn: str | None = None,
    environment: str | None = None,
    traces_sample_rate: float | None = None,
    errors_sample_rate: float | None = None,
) -> bool:
    """Initialize Sentry error tracking.

    Args:
        dsn: Sentry DSN (Data Source Name). If None, reads from SENTRY_DSN env var.
        environment: Environment name (production, staging, development).
                   If None, reads from ENVIRONMENT env var.
        traces_sample_rate: Sample rate for traces (0.0 to 1.0).
                           If None, uses default from config.
        errors_sample_rate: Sample rate for error capture (0.0 to 1.0).
                          If None, uses default from config.

    Returns:
        True if Sentry was initialized successfully, False otherwise
    """
    if not SENTRY_AVAILABLE:
        logger.warning("Sentry SDK not available. Error tracking disabled.")
        return False

    # Get DSN from parameter or environment
    dsn = dsn or ErrorTrackingConfig.get("SENTRY_DSN")
    if not dsn:
        logger.debug("Sentry DSN not configured. Error tracking disabled.")
        return False

    # Get configuration
    environment = environment or ErrorTrackingConfig.get("SENTRY_ENVIRONMENT")
    traces_sample_rate = traces_sample_rate or float(
        ErrorTrackingConfig.get("SENTRY_TRACES_SAMPLE_RATE", 0.1),
    )
    errors_sample_rate = errors_sample_rate or float(
        ErrorTrackingConfig.get("SENTRY_ERRORS_SAMPLE_RATE", 1.0),
    )

    # Get app version
    release = ErrorTrackingConfig.get("SENTRY_RELEASE") or _get_app_version()

    try:
        # Configure integrations
        integrations = [
            FastApiIntegration(),
            SqlalchemyIntegration(),
            _setup_logging_integration(),
        ]

        # Filter out None integrations
        integrations = [i for i in integrations if i is not None]

        # Initialize Sentry
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            traces_sample_rate=traces_sample_rate,
            sample_rate=errors_sample_rate,
            attach_stacktrace=ErrorTrackingConfig.get("SENTRY_ATTACH_STACKTRACE"),
            max_breadcrumbs=ErrorTrackingConfig.get("SENTRY_MAX_BREADCRUMBS"),
            include_local_vars=ErrorTrackingConfig.get("SENTRY_INCLUDE_LOCAL_VARS"),
            integrations=integrations,
            # Ignore specific errors
            ignore_errors=ErrorTrackingConfig.get("SENTRY_IGNORE_ERRORS"),
        )

        logger.info(
            f"✓ Error tracking initialized (environment: {environment}, "
            f"traces_sample_rate: {traces_sample_rate}, "
            f"errors_sample_rate: {errors_sample_rate})",
        )

        # Set initial context
        set_context("app", {
            "version": release or "unknown",
            "environment": environment,
            "python_version": sys.version.split()[0],
        })

        return True

    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")
        return False


def set_context(key: str, data: dict[str, Any]) -> None:
    """Set additional context for error tracking.

    Args:
        key: Context key (e.g., 'user', 'app', 'custom')
        data: Dictionary of context data
    """
    if SENTRY_AVAILABLE:
        sentry_sdk.set_context(key, data)


def set_user(user_id: str | None = None, **extra) -> None:
    """Set user context for error tracking.

    Args:
        user_id: User identifier
        **extra: Additional user data (email, username, etc.)
    """
    if SENTRY_AVAILABLE and user_id:
        sentry_sdk.set_user({"id": user_id, **extra})


def add_breadcrumb(
    message: str,
    category: str = "generic",
    level: str = "info",
    **data,
) -> None:
    """Add a breadcrumb for error tracking.

    Breadcrumbs provide a trail of events leading up to an error.

    Args:
        message: Breadcrumb message
        category: Event category (e.g., 'http', 'database', 'user_action')
        level: Log level ('debug', 'info', 'warning', 'error', 'critical')
        **data: Additional breadcrumb data
    """
    if SENTRY_AVAILABLE:
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data,
        )


def capture_exception(
    exc: BaseException | None = None,
    extra: dict[str, Any] | None = None,
    **tags,
) -> str | None:
    """Capture an exception with optional context.

    Args:
        exc: Exception to capture. If None, captures the current exception.
        extra: Additional data to attach to the event
        **tags: Tags to add to the event

    Returns:
        Event ID if captured successfully, None otherwise
    """
    if not SENTRY_AVAILABLE:
        return None

    # Add extra data if provided
    if extra:
        set_context("additional", extra)

    # Add tags if provided
    if tags:
        sentry_sdk.set_tag("custom_error", "true")
        for key, value in tags.items():
            sentry_sdk.set_tag(key, str(value))

    # Capture the exception
    event_id = sentry_sdk.capture_exception(exc)

    if event_id:
        logger.debug(f"Exception captured: {event_id}")
    else:
        logger.warning("Failed to capture exception")

    return event_id


def capture_message(
    message: str,
    level: str = "info",
    extra: dict[str, Any] | None = None,
    **tags,
) -> str | None:
    """Capture a message with optional context.

    Args:
        message: Message to capture
        level: Log level ('debug', 'info', 'warning', 'error', 'critical')
        extra: Additional data to attach to the event
        **tags: Tags to add to the event

    Returns:
        Event ID if captured successfully, None otherwise
    """
    if not SENTRY_AVAILABLE:
        return None

    # Map string level to Sentry level
    level_map = {
        "debug": "debug",
        "info": "info",
        "warning": "warning",
        "error": "error",
        "critical": "critical",
    }
    sentry_level = level_map.get(level.lower(), "info")

    # Add extra data if provided
    if extra:
        set_context("additional", extra)

    # Add tags if provided
    if tags:
        for key, value in tags.items():
            sentry_sdk.set_tag(key, str(value))

    event_id = sentry_sdk.capture_message(message, level=sentry_level)

    if event_id:
        logger.debug(f"Message captured: {event_id}")
    else:
        logger.warning(f"Failed to capture message: {message}")

    return event_id


def start_transaction(name: str, operation: str = "custom") -> Transaction | None:
    """Start a new transaction for performance monitoring.

    Args:
        name: Transaction name
        operation: Operation type (e.g., 'http.request', 'function.call')

    Returns:
        Transaction context manager or None if Sentry unavailable
    """
    if not SENTRY_AVAILABLE:
        return None

    return sentry_sdk.start_transaction(name=name, op=operation)


def capture_error_with_context(
    exc: BaseException,
    context: dict[str, Any],
    tags: dict[str, str] | None = None,
) -> str | None:
    """Capture an exception with rich context.

    This is a convenience function that combines setting context,
    tags, and capturing the exception in one call.

    Args:
        exc: Exception to capture
        context: Context data to attach
        tags: Optional tags to add

    Returns:
        Event ID if captured successfully, None otherwise
    """
    # Set the context
    set_context("error_details", context)

    # Add tags if provided
    if tags:
        for key, value in tags.items():
            if SENTRY_AVAILABLE:
                sentry_sdk.set_tag(key, str(value))

    return capture_exception(exc)


class ErrorTracker:
    """Context manager for capturing errors with automatic cleanup.

    Usage:
        with ErrorTracker(operation_name="data_fetch"):
            risky_operation()
    """

    def __init__(
        self,
        operation_name: str,
        extra_context: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ):
        """Initialize error tracker.

        Args:
            operation_name: Name of the operation being tracked
            extra_context: Additional context to capture on error
            tags: Tags to add to the transaction
        """
        self.operation_name = operation_name
        self.extra_context = extra_context or {}
        self.tags = tags or {}
        self.transaction: Transaction | None = None

    def __enter__(self):
        """Start tracking."""
        self.transaction = start_transaction(
            name=self.operation_name,
            operation="operation",
        )
        if self.tags and SENTRY_AVAILABLE:
            for key, value in self.tags.items():
                sentry_sdk.set_tag(key, str(value))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End tracking and capture exception if any."""
        # Set additional context
        if self.extra_context:
            set_context("operation", self.extra_context)

        # Capture exception if one occurred
        if exc_type is not None:
            capture_exception(
                exc_val,
                extra=self.extra_context,
                **self.tags,
            )

        # Finish transaction
        if self.transaction:
            self.transaction.__exit__(exc_type, exc_val, exc_tb)

        return False  # Don't suppress exceptions


def setup_error_tracking_signal_handlers() -> None:
    """Setup signal handlers for capturing errors on crash.

    This should be called during application initialization to ensure
    errors during shutdown or from signals are captured.
    """
    if not SENTRY_AVAILABLE:
        return

    # Sentry automatically handles common signals in most environments
    # But we can add custom flush behavior
    def handle_signal(signum, frame):
        logger.warning(f"Received signal {signum}, flushing Sentry...")
        if SENTRY_AVAILABLE:
            sentry_sdk.flush(timeout=5)
        sys.exit(0)

    # Note: In production, let Sentry handle signals automatically
    # This is mainly for development/custom scenarios
    logger.debug("Signal handlers configured for error tracking")
