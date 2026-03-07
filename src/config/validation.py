"""Configuration validation functions.

Provides functions to validate external service URLs and critical environment
variables at startup.
"""

import os

from src.config.config_manager import ConfigManager


def get_ollama_url() -> str:
    """Get Ollama local inference server URL from environment via ConfigManager."""
    return ConfigManager.get("OLLAMA_URL")


def get_traceloop_url() -> str:
    """Get Traceloop collector URL from environment via ConfigManager."""
    return ConfigManager.get("TRACELOOP_URL")


def get_telegram_api_url() -> str:
    """Get Telegram Bot API base URL from environment via ConfigManager."""
    return ConfigManager.get("TELEGRAM_API_URL")


def validate_urls() -> None:
    """Validate that all external service URLs are properly configured.

    Checks that URLs are:
    - Not empty
    - Valid URL format (starts with http:// or https://)

    Raises:
        ValueError: If any URL is invalid or misconfigured
    """
    urls = {
        "OLLAMA_URL": get_ollama_url(),
        "TRACELOOP_URL": get_traceloop_url(),
        "TELEGRAM_API_URL": get_telegram_api_url(),
    }

    for name, url in urls.items():
        if not url:
            raise ValueError(f"{name} is not configured")

        if not (url.startswith(("http://", "https://"))):
            raise ValueError(
                f"{name}={url} is invalid. Must start with http:// or https://",
            )


def validate_critical_env_vars() -> None:
    """Validate that all critical environment variables are set.

    This function checks for required variables that would cause runtime failures
    if missing. Fails loudly on startup rather than silently at runtime.

    Raises:
        ValueError: If any critical environment variable is missing or invalid
    """
    errors = []

    # Check for LLM API configuration
    # Either API_KEY or OPENAI_API_KEY must be set for cloud models
    if not os.getenv("API_KEY") and not os.getenv("OPENAI_API_KEY"):
        errors.append(
            "LLM API key not configured: set either API_KEY or OPENAI_API_KEY",
        )

    # Check for Stripe configuration in non-development mode
    env_type = os.getenv("ENV", "development").lower()
    if env_type == "production":
        if not os.getenv("STRIPE_SECRET_KEY"):
            errors.append("STRIPE_SECRET_KEY not set (required in production)")

        if not os.getenv("STRIPE_WEBHOOK_SECRET"):
            errors.append("STRIPE_WEBHOOK_SECRET not set (required in production)")

        if not os.getenv("DATABASE_URL"):
            errors.append("DATABASE_URL not set (required in production)")

    # Warn about insecure defaults
    client_secret = os.getenv("CLIENT_AUTH_SECRET", "")
    if client_secret == "CHANGE_ME_IN_PRODUCTION_use_a_random_32_byte_key":  # noqa: S105 - This is a security check, not a hardcoded password
        if env_type == "production":
            errors.append(
                "CLIENT_AUTH_SECRET using insecure default in production. "
                "Generate a secure key: openssl rand -hex 32",
            )

    # Validate delivery token configuration
    try:
        int(os.getenv("DELIVERY_TOKEN_TTL_HOURS", "1"))
        int(os.getenv("DELIVERY_MAX_FAILED_ATTEMPTS", "5"))
        int(os.getenv("DELIVERY_LOCKOUT_SECONDS", "3600"))
        int(os.getenv("DELIVERY_MAX_ATTEMPTS_PER_IP", "20"))
        int(os.getenv("DELIVERY_IP_LOCKOUT_SECONDS", "3600"))
    except ValueError as e:
        errors.append(f"Invalid delivery token configuration: {e}")

    # Validate bid amount configuration
    try:
        min_bid = int(os.getenv("MIN_BID_AMOUNT", "1000"))
        max_bid = int(os.getenv("MAX_BID_AMOUNT", "50000"))
        if min_bid > max_bid:
            errors.append(
                f"Invalid bid amounts: MIN_BID_AMOUNT ({min_bid}) > "
                f"MAX_BID_AMOUNT ({max_bid})",
            )
    except ValueError as e:
        errors.append(f"Invalid bid amount configuration: {e}")

    # Validate timeout configurations
    try:
        int(os.getenv("DOCKER_SANDBOX_TIMEOUT", "120"))
        int(os.getenv("MARKET_SCAN_PAGE_TIMEOUT", "30"))
        int(os.getenv("MARKET_SCAN_INTERVAL", "300"))
    except ValueError as e:
        errors.append(f"Invalid timeout configuration: {e}")

    # Validate boolean flags
    for flag in [
        "USE_DOCKER_SANDBOX",
        "USE_LOCAL_BY_DEFAULT",
        "AUTONOMOUS_SCAN_ENABLED",
        "ENABLE_DISTILLATION_CAPTURE",
    ]:
        value = os.getenv(flag, "").lower()
        if value and value not in {"true", "false", "yes", "no", "1", "0"}:
            errors.append(f"Invalid boolean value for {flag}={value}")

    # Validate logging level
    valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    if log_level not in valid_log_levels:
        errors.append(
            f"Invalid LOG_LEVEL={log_level}. Must be one of {valid_log_levels}",
        )

    # Raise all errors at once for better visibility
    if errors:
        error_message = "Configuration validation failed:\n  " + "\n  ".join(errors)
        raise ValueError(error_message)


__all__ = [
    "validate_critical_env_vars",
    "validate_urls",
]
