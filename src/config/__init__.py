"""Configuration Management.

Centralized configuration loading from environment variables with defaults.
Supports both local development and production deployments.
"""

from src.config.config_manager import ConfigManager, ValidationError, get_config
from src.config.helpers import (
    get_all_configured_env_vars,
    get_database_url,
    get_log_level,
    get_max_bid_amount,
    get_min_bid_amount,
    get_openai_api_key,
    get_redis_url,
    get_stripe_secret_key,
    get_stripe_webhook_secret,
    is_debug,
    should_use_redis_locks,
)
from src.config.urls import get_ollama_url, get_telegram_api_url, get_traceloop_url
from src.config.validation import validate_critical_env_vars, validate_urls

# Alias for backward compatibility
Config = ConfigManager

__all__ = [
    "ConfigManager",
    "Config",
    "ValidationError",
    "get_all_configured_env_vars",
    "get_config",
    "get_database_url",
    "get_log_level",
    "get_max_bid_amount",
    "get_min_bid_amount",
    "get_ollama_url",
    "get_openai_api_key",
    "get_redis_url",
    "get_stripe_secret_key",
    "get_stripe_webhook_secret",
    "get_telegram_api_url",
    "get_traceloop_url",
    "is_debug",
    "should_use_redis_locks",
    "validate_critical_env_vars",
    "validate_urls",
]
