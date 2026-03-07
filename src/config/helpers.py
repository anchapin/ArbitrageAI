"""Configuration helper functions.

Provides utility functions to retrieve various configuration values from
environment variables.
"""

import os
import re


def get_redis_url() -> str:
    """Get Redis connection URL from environment.

    Priority order:
    1. REDIS_URL env variable (format: redis://host:port/db)
    2. Separate REDIS_HOST, REDIS_PORT, REDIS_DB variables
    3. Default: redis://localhost:6379/0 (local development)

    Returns:
        Redis connection URL

    Raises:
        ValueError: If Redis connection cannot be determined
    """
    # Try explicit URL first
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return redis_url

    # Try component-based config
    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    db = os.getenv("REDIS_DB", "0")
    password = os.getenv("REDIS_PASSWORD", "")

    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


def get_database_url() -> str:
    """Get SQLAlchemy database URL from environment.

    Default: SQLite at data/tasks.db (local development)

    Returns:
        Database URL
    """
    return os.getenv("DATABASE_URL", "sqlite:///./data/tasks.db")


def get_openai_api_key() -> str:
    """Get OpenAI API key from environment."""
    api_key = os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("API_KEY or OPENAI_API_KEY environment variable not set")
    return api_key


def get_stripe_secret_key() -> str:
    """Get Stripe secret key from environment."""
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        raise ValueError("STRIPE_SECRET_KEY environment variable not set")
    return key


def get_stripe_webhook_secret() -> str:
    """Get Stripe webhook secret from environment."""
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise ValueError("STRIPE_WEBHOOK_SECRET environment variable not set")
    return secret


def is_debug() -> bool:
    """Check if debug mode is enabled."""
    return os.getenv("DEBUG", "false").lower() in {"true", "1", "yes"}


def get_log_level() -> str:
    """Get log level from environment."""
    return os.getenv("LOG_LEVEL", "INFO")


def get_max_bid_amount() -> int:
    """Get max bid amount in cents from environment."""
    return int(os.getenv("MAX_BID_AMOUNT", "50000"))  # $500 default


def get_min_bid_amount() -> int:
    """Get min bid amount in cents from environment."""
    return int(os.getenv("MIN_BID_AMOUNT", "1000"))  # $10 default


def should_use_redis_locks() -> bool:
    """Determine if Redis-backed distributed locks should be used.

    Priority:
    1. USE_REDIS_LOCKS env variable (explicit override)
    2. REDIS_URL availability (try to auto-detect)
    3. Default: True for production, False for development

    Returns:
        True if Redis locks should be used, False for in-memory fallback
    """
    # Explicit override
    use_redis = os.getenv("USE_REDIS_LOCKS")
    if use_redis is not None:
        return use_redis.lower() in {"true", "1", "yes"}

    # Check if REDIS_URL or Redis config is available
    if os.getenv("REDIS_URL"):
        return True

    if os.getenv("REDIS_HOST") or os.getenv("REDIS_PORT"):
        return True

    # Default: use Redis unless in development mode
    is_dev = os.getenv("ENV", "development").lower() == "development"
    return not is_dev


def get_all_configured_env_vars() -> dict:
    """Get a summary of all environment variables used in the application.

    Returns:
        Dictionary mapping variable names to their current values (with secrets masked)
    """
    # All known environment variables in the application
    all_vars = {
        # Database
        "DATABASE_URL": "sqlite:///./data/tasks.db",
        "REDIS_URL": None,
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "REDIS_DB": "0",
        "REDIS_PASSWORD": None,
        "USE_REDIS_LOCKS": None,
        # LLM
        "API_KEY": None,
        "OPENAI_API_KEY": None,
        "BASE_URL": "https://api.openai.com/v1",
        "CLOUD_MODEL": "gpt-4o-mini",
        "LOCAL_BASE_URL": "http://localhost:11434/v1",
        "LOCAL_API_KEY": "not-needed",
        "LOCAL_MODEL": "llama3.2",
        "USE_LOCAL_BY_DEFAULT": "false",
        "TASK_MODEL_MAP": "{}",
        "TASK_USE_LOCAL_MAP": "{}",
        "OLLAMA_URL": "http://localhost:11434/v1",
        "MIN_CLOUD_REVENUE": "3000",
        # Marketplace
        "MARKETPLACES_FILE": "data/marketplaces.json",
        "MARKETPLACE_URL": None,
        "AUTONOMOUS_SCAN_ENABLED": "false",
        "MARKET_SCAN_MODEL": "llama3.2",
        "MARKET_SCAN_PAGE_TIMEOUT": "30",
        "MARKET_SCAN_INTERVAL": "300",
        "MAX_BID_AMOUNT": "50000",
        "MIN_BID_AMOUNT": "1000",
        # Sandbox
        "USE_DOCKER_SANDBOX": "true",
        "DOCKER_SANDBOX_IMAGE": "ai-sandbox-base",
        "DOCKER_SANDBOX_TIMEOUT": "120",
        "E2B_API_KEY": None,
        # Payment
        "STRIPE_SECRET_KEY": None,
        "STRIPE_WEBHOOK_SECRET": None,
        "STRIPE_PUBLISHABLE_KEY": None,
        # Delivery tokens
        "DELIVERY_TOKEN_TTL_HOURS": "1",
        "DELIVERY_MAX_FAILED_ATTEMPTS": "5",
        "DELIVERY_LOCKOUT_SECONDS": "3600",
        "DELIVERY_MAX_ATTEMPTS_PER_IP": "20",
        "DELIVERY_IP_LOCKOUT_SECONDS": "3600",
        # Authentication
        "CLIENT_AUTH_SECRET": None,
        # Notifications
        "TELEGRAM_BOT_TOKEN": None,
        "TELEGRAM_CHAT_ID": None,
        "TELEGRAM_API_URL": "https://api.telegram.org",
        # Security
        "ANTIVIRUS_SERVICE": "mock",
        "VIRUSTOTAL_API_KEY": None,
        # Observability
        "ENVIRONMENT": "development",
        "ENV": "development",
        "DEBUG": "false",
        "LOG_LEVEL": "INFO",
        "TRACELOOP_URL": "http://localhost:6006/v1/traces",
        # Distillation
        "ENABLE_DISTILLATION_CAPTURE": "true",
        # General
        "CORS_ORIGINS": "http://localhost:5173",
    }

    # Build result with current values
    result = {}
    secret_patterns = [
        "API_KEY",
        "SECRET",
        "TOKEN",
        "PASSWORD",
        "WEBHOOK",
        "STRIPE",
    ]

    for var_name, default_value in all_vars.items():
        current_value = os.getenv(var_name)

        # Determine what to display
        if current_value is not None:
            display_value = current_value
        elif default_value is not None:
            display_value = default_value
        else:
            display_value = "(not set)"

        # Mask secrets
        is_secret = any(
            re.search(pattern, var_name, re.IGNORECASE) for pattern in secret_patterns
        )
        if is_secret and display_value != "(not set)":
            display_value = (
                "***" + display_value[-4:] if len(display_value) > 4 else "***"
            )

        result[var_name] = display_value

    return result


__all__ = [
    "get_all_configured_env_vars",
    "get_database_url",
    "get_log_level",
    "get_max_bid_amount",
    "get_min_bid_amount",
    "get_openai_api_key",
    "get_redis_url",
    "get_stripe_secret_key",
    "get_stripe_webhook_secret",
    "is_debug",
    "should_use_redis_locks",
]
