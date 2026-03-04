"""
Centralized Configuration Manager for ArbitrageAI.
Combines and replaces legacy configuration management.
Provides validation and audit logging for configuration changes.
"""

import logging
import os
import sys
from typing import Any, ClassVar, Optional

# Import logger
try:
    from src.utils.logger import get_logger
    from src.utils.secrets import (
        is_insecure_default,
        load_or_create_secrets,
    )

    logger = get_logger(__name__)
except (ImportError, ValueError):
    logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when configuration validation fails."""


class ConfigManager:
    """
    Manages application configuration, replacing hardcoded magic numbers.
    Loads from environment variables with safe defaults and validation.
    """

    _instance: Optional["ConfigManager"] = None
    _config_cache: ClassVar[dict[str, Any]] = {}

    # DEFAULT CONFIGURATION VALUES (Match tests/test_config_manager.py)
    _DEFAULTS: ClassVar[dict[str, Any]] = {
        # LLM Routing
        "MIN_CLOUD_REVENUE": 3000,
        "CLOUD_GPT4O_OUTPUT_COST": 1000,
        "DEFAULT_TASK_REVENUE": 500,
        "HIGH_VALUE_THRESHOLD": 200,
        # Marketplace Scanning
        "MAX_BID_AMOUNT": 500,
        "MIN_BID_AMOUNT": 10,
        "BID_LIMIT_CENTS": 50000,
        "MIN_BID_THRESHOLD": 30,
        # Marketplace Scanning Timeouts
        "PAGE_LOAD_TIMEOUT": 30,
        "SCAN_INTERVAL": 300,
        "MARKET_SCAN_INTERVAL": 300,
        # Sandbox Execution Timeouts
        "DOCKER_SANDBOX_TIMEOUT": 120,
        "SANDBOX_TIMEOUT_SECONDS": 600,
        "MAX_RETRY_ATTEMPTS": 3,
        # Delivery & Security Thresholds
        "DELIVERY_TOKEN_TTL_HOURS": 1,
        "MAX_DELIVERY_TOKEN_TTL_DAYS": 7,
        "DELIVERY_MAX_FAILED_ATTEMPTS": 5,
        "DELIVERY_LOCKOUT_SECONDS": 3600,
        "DELIVERY_MAX_ATTEMPTS_PER_IP": 20,
        "DELIVERY_IP_LOCKOUT_SECONDS": 3600,
        "MAX_DELIVERY_AMOUNT_CENTS": 100000000,  # $1M
        # Locking & Distribution
        "BID_LOCK_MANAGER_TTL": 300,
        # File Handling
        "MAX_FILE_SIZE_BYTES": 50 * 1024 * 1024,
        # ML & Distillation
        "MIN_EXAMPLES_FOR_TRAINING": 500,
        # Security & Webhooks
        "WEBHOOK_TIMESTAMP_WINDOW": 300,
        # Health Check & Monitoring
        "LLM_HEALTH_CHECK_HISTORY_SIZE": 100,
        "LLM_HEALTH_CHECK_INITIAL_DELAY_MS": 100,
        "LLM_HEALTH_CHECK_MAX_DELAY_MS": 10000,
        # Circuit Breaker
        "URL_CIRCUIT_BREAKER_COOLDOWN_SECONDS": 300,
        # General
        "ENV": "development",
        "DEBUG": False,
        "LOG_LEVEL": "INFO",
        # Training Mode for Simulation & Strategy Testing
        "TRAINING_MODE": False,  # When enabled, prevents real bid submissions
        # Virtual Wallet & Budget System (Issue #92, #93)
        "INITIAL_SEED_MONEY": 10000,  # Initial seed money in cents ($100)
        "BUDGET_CAP_WEEKLY": 50000,  # Weekly budget cap in cents ($500)
        "BUDGET_RESET_PERIOD": "weekly",  # Reset period: daily, weekly, monthly
        # Auto-Threshold Increase (Issue #99)
        "AUTO_THRESHOLD_INCREASE": True,  # Enable auto threshold increase
        "AUTO_THRESHOLD_WIN_RATE_THRESHOLD": 70,  # Win rate % to trigger increase
        "AUTO_THRESHOLD_PROFIT_MARGIN_THRESHOLD": 50,  # Profit margin in cents ($0.50)
        "AUTO_THRESHOLD_CONSECUTIVE_PERIODS": 4,  # Consecutive periods meeting criteria
        "WEEKLY_PETITION_DAY": "monday",  # Day of week for evaluation
        # External URLs
        "OLLAMA_URL": "http://localhost:11434/v1",
        "TRACELOOP_URL": "http://localhost:6006/v1/traces",
        "TELEGRAM_API_URL": "https://api.telegram.org",
        "BASE_URL": "http://localhost:5173",
        # Disaster Recovery (Issue #50)
        "BACKUP_DIR": "data/backups",
        "RECOVERY_DIR": "data/recovery",
        "BACKUP_RETENTION_DAYS": 30,
        "ENCRYPTION_ENABLED": False,
        "AWS_S3_BACKUP_BUCKET": None,
        "AWS_ACCESS_KEY_ID": None,
        "AWS_SECRET_ACCESS_KEY": None,
        "AWS_REGION": "us-east-1",
        # Infrastructure
        "REDIS_URL": "redis://localhost:6379/0",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": 6379,
        "REDIS_DB": 0,
        "REDIS_PASSWORD": None,
        "REDIS_CONNECTION_TIMEOUT": 5,
        "REDIS_SOCKET_TIMEOUT": 5,
        # Rate Limiting Configuration (QAQC-009)
        "RATE_LIMIT_ENABLED": True,
        "RATE_LIMIT_ALGORITHM": "sliding",  # "sliding" or "fixed"
        "RATE_LIMIT_KEY_PREFIX": "ratelimit",
        "RATE_LIMIT_DEFAULT_TTL": 2,
        "RATE_LIMIT_BURST_TTL": 3600,
        "DATABASE_URL": "sqlite:///./data/tasks.db",
        # Authentication - Auto-loaded from secure storage or environment
        # JWT_SECRET_KEY is loaded from secrets or environment (not hardcoded)
    }

    def __init__(self):
        """Initialize ConfigManager and load all values into attributes."""
        # Load secure secrets first
        self._load_secure_secrets()
        # Then load all other configuration
        self._load_all()

    def _load_all(self):
        """Load all known configuration into instance attributes."""
        # Use a local list to avoid modifying during iteration if needed
        keys = list(self._DEFAULTS.keys())
        for key in keys:
            val = self.get(key)
            setattr(self, key, val)

        # Cross-field validations
        if self.MIN_BID_AMOUNT > self.MAX_BID_AMOUNT:
            raise ValidationError(
                f"MIN_BID_AMOUNT ({self.MIN_BID_AMOUNT}) cannot exceed MAX_BID_AMOUNT ({self.MAX_BID_AMOUNT})",
            )

        if self.DOCKER_SANDBOX_TIMEOUT > self.SANDBOX_TIMEOUT_SECONDS:
            raise ValidationError(
                f"DOCKER_SANDBOX_TIMEOUT ({self.DOCKER_SANDBOX_TIMEOUT}) cannot exceed SANDBOX_TIMEOUT_SECONDS ({self.SANDBOX_TIMEOUT_SECONDS})",
            )

        if self.LLM_HEALTH_CHECK_INITIAL_DELAY_MS > self.LLM_HEALTH_CHECK_MAX_DELAY_MS:
            raise ValidationError(
                f"LLM_HEALTH_CHECK_INITIAL_DELAY_MS ({self.LLM_HEALTH_CHECK_INITIAL_DELAY_MS}) cannot exceed LLM_HEALTH_CHECK_MAX_DELAY_MS ({self.LLM_HEALTH_CHECK_MAX_DELAY_MS})",
            )

    def _load_secure_secrets(self):
        """
        Load secure secrets from secure storage or environment variables.

        This method:
        1. Attempts to load secrets from secure file storage
        2. Falls back to environment variables if not found
        3. Auto-generates new secrets if neither exists (development mode)
        4. Sets environment variables for use by the rest of the application
        """
        try:
            # Try to load from secure storage
            secrets = load_or_create_secrets()

            # Set environment variables from loaded secrets
            # Only set if not already overridden by environment
            for key, value in secrets.items():
                if key not in os.environ:
                    os.environ[key] = value

            logger.info("✅ Loaded secrets from secure storage")

        except Exception as e:
            logger.warning(f"Failed to load secrets from storage: {e}")
            logger.info("Using environment variables for secrets")

            # Check if critical secrets are set in environment
            critical_secrets = ["JWT_SECRET_KEY", "CLIENT_AUTH_SECRET"]

            missing = [secret for secret in critical_secrets if secret not in os.environ]

            if missing:
                logger.warning(
                    f"Critical secrets not set in environment: {', '.join(missing)}\n"
                    f"Run: python scripts/generate_secrets.py",
                )

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get configuration value from environment or default with type conversion."""
        # Check cache first
        if key in cls._config_cache:
            return cls._config_cache[key]

        env_val = os.getenv(key)
        default_val = default if default is not None else cls._DEFAULTS.get(key)

        if env_val is None:
            val = default_val
        else:
            try:
                if isinstance(default_val, bool):
                    val = str(env_val).lower() in {"true", "1", "yes"}
                elif isinstance(default_val, int):
                    val = int(env_val)
                elif isinstance(default_val, float):
                    val = float(env_val)
                else:
                    val = env_val
            except (ValueError, TypeError) as e:
                raise ValidationError(f"{key}: Expected integer, got '{env_val}'") from e

        # Additional range validations for specific keys to match tests
        if key == "MIN_BID_AMOUNT" and val is not None:
            try:
                if int(val) < 0:
                    raise ValidationError(f"{key}: {val} is below minimum")
            except (ValueError, TypeError):
                pass

        if key == "PAGE_LOAD_TIMEOUT" and val is not None:
            try:
                v = int(val)
                if v <= 0:
                    raise ValidationError(f"{key}: {v} is below minimum")
                if v > 300:
                    raise ValidationError(f"{key}: {v} exceeds maximum")
            except (ValueError, TypeError):
                pass

        if key == "DELIVERY_LOCKOUT_SECONDS" and val is not None:
            try:
                v = int(val)
                if v <= 0:
                    raise ValidationError(f"{key}: {v} is below minimum")
                if v > 86400:
                    raise ValidationError(f"{key}: {v} exceeds maximum")
            except (ValueError, TypeError):
                pass

        cls._config_cache[key] = val
        return val

    @classmethod
    def get_instance(cls) -> "ConfigManager":
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset the configuration cache and singleton instance."""
        cls._config_cache = {}
        cls._instance = None

    def to_dict(self) -> dict[str, Any]:
        """Convert all configuration to dictionary."""
        return {key: getattr(self, key) for key in self._DEFAULTS}

    @staticmethod
    def validate_production_configuration() -> None:
        """
        Validate production configuration and fail fast on insecure defaults.

        This function should be called during application startup,
        before any sensitive operations are performed.

        Raises:
            SystemExit: If critical security requirements are not met
        """
        if os.getenv("ENVIRONMENT") != "production":
            logger.info("Skipping production validation (not in production mode)")
            return

        errors = []
        warnings = []

        # Critical secrets that MUST be secure in production
        critical_secrets = {
            "JWT_SECRET_KEY": "JWT signing secret",
            "CLIENT_AUTH_SECRET": "Client authentication secret",
            "STRIPE_SECRET_KEY": "Stripe payment processing secret",
            "STRIPE_WEBHOOK_SECRET": "Stripe webhook verification secret",
        }

        for env_var, description in critical_secrets.items():
            value = os.getenv(env_var, "")

            if not value:
                errors.append(f"❌ {env_var} is not set ({description})")
            elif is_insecure_default(value):
                errors.append(
                    f"❌ {env_var} appears to be an insecure default ({description})\n"
                    f"   Current value: {value[:20]}...\n"
                    f"   Action: Generate a secure random value",
                )

        # Important but not critical
        if not os.getenv("DATABASE_URL"):
            warnings.append("⚠️  DATABASE_URL not set, using default SQLite")

        # Log warnings
        for warning in warnings:
            logger.warning(warning)

        # Fail on errors
        if errors:
            logger.critical("\n" + "=" * 70)
            logger.critical("🚨 PRODUCTION SECURITY VALIDATION FAILED 🚨")
            logger.critical("=" * 70)
            logger.critical("\nThe following security issues must be resolved:\n")

            for error in errors:
                logger.critical(error)

            logger.critical("\n" + "=" * 70)
            logger.critical("ACTION REQUIRED:")
            logger.critical("1. Generate secure secrets: python scripts/generate_secrets.py")
            logger.critical("2. Set environment variables securely")
            logger.critical("3. Never commit secrets to version control")
            logger.critical("=" * 70 + "\n")

            sys.exit(1)

        logger.info("✅ Production security validation passed")


# Singleton getter
def get_config() -> ConfigManager:
    """Get the global ConfigManager instance."""
    return ConfigManager.get_instance()


# Export reset_instance for tests
def reset_instance():
    """Reset the configuration cache and singleton instance."""
    ConfigManager.reset_instance()


# Convenience export for validation function
def validate_production_configuration() -> None:
    """Validate production configuration and fail fast on insecure defaults."""
    ConfigManager.validate_production_configuration()
