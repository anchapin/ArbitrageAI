"""
Secure Secret Management Module.

Provides secure generation and storage of cryptographic secrets.
Used for JWT secrets, API keys, and other sensitive configuration values.

Security Features:
- Cryptographically secure random generation using secrets.token_hex()
- Secure file storage with restricted permissions (0o600)
- Automatic secret generation on first startup
- Audit logging for secret operations
"""

import json
from pathlib import Path
import secrets

from .logger import get_logger

logger = get_logger(__name__)

# Secure secrets file location
SECRETS_FILE = Path("data/.secrets")

# Insecure default patterns to detect and reject
# These are specific patterns that indicate placeholder/test values
INSECURE_DEFAULTS = {
    "change_me_in_production",  # Case-insensitive matching applied
    "your-secret-key-here",
    "your-jwt-secret-here",
    "your-openai-api-key-here",
    "sk_test_",  # Stripe test keys (not sk_live_)
    "pk_test_",  # Stripe test publishable keys
    "whsec_test",  # Stripe test webhook secrets (whsec_ prefix alone is valid for prod)
    "password",
    "admin",
    "12345678",
    "placeholder",
    "test_secret",
    "test_key",
    "test_value",
}


def generate_secure_secret() -> str:
    """
    Generate a cryptographically secure random secret.

    Returns:
        str: 256-bit (64 character hex) secure random secret
    """
    return secrets.token_hex(32)  # 256-bit secret


def _load_secrets() -> dict[str, str]:
    """
    Load secrets from secure file.

    Returns:
        Dict containing loaded secrets

    Raises:
        FileNotFoundError: If secrets file doesn't exist
        PermissionError: If file permissions are incorrect
    """
    if not SECRETS_FILE.exists():
        raise FileNotFoundError(f"Secrets file not found: {SECRETS_FILE}")

    # Check file permissions (should be owner read/write only)
    file_mode = SECRETS_FILE.stat().st_mode & 0o777
    if file_mode != 0o600:
        logger.warning(
            f"Secrets file has insecure permissions: {oct(file_mode)}. "
            f"Expected 0o600. Fixing permissions.",
        )
        SECRETS_FILE.chmod(0o600)

    with open(SECRETS_FILE, encoding="utf-8") as f:
        secrets_dict = json.load(f)

    logger.info(f"Loaded {len(secrets_dict)} secrets from secure storage")
    return secrets_dict


def _save_secrets(secrets_dict: dict[str, str]) -> None:
    """
    Save secrets to secure file with restricted permissions.

    Args:
        secrets_dict: Dictionary of secrets to save

    Security:
        - Creates parent directories if needed
        - Sets file permissions to 0o600 (owner read/write only)
        - Logs operation for audit trail
    """
    # Create directory if it doesn't exist
    SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write secrets to file
    with open(SECRETS_FILE, "w", encoding="utf-8") as f:
        json.dump(secrets_dict, f, indent=2)

    # Set secure permissions (owner read/write only)
    SECRETS_FILE.chmod(0o600)

    logger.info(f"Saved {len(secrets_dict)} secrets to secure storage at {SECRETS_FILE}")
    logger.warning("⚠️  IMPORTANT: Back up secrets file securely and never commit to version control!")


def load_or_create_secrets() -> dict[str, str]:
    """
    Load existing secrets or create new ones if they don't exist.

    This function should be called during application startup to ensure
    all required secrets are available.

    Returns:
        Dict containing all required secrets

    Secrets Generated:
        - JWT_SECRET_KEY: For JWT token signing
        - CLIENT_AUTH_SECRET: For client authentication
        - DATABASE_ENCRYPTION_KEY: For database encryption
    """
    try:
        return _load_secrets()
    except FileNotFoundError:
        logger.info("No existing secrets found, generating new secure secrets...")

        new_secrets = {
            "JWT_SECRET_KEY": generate_secure_secret(),
            "CLIENT_AUTH_SECRET": generate_secure_secret(),
            "DATABASE_ENCRYPTION_KEY": generate_secure_secret(),
        }

        _save_secrets(new_secrets)

        logger.info("✅ Generated new secure secrets")
        return new_secrets


def is_insecure_default(value: str) -> bool:
    """
    Check if a value appears to be an insecure default.

    Args:
        value: The secret value to check

    Returns:
        True if the value appears to be an insecure default

    Checks:
        - Empty or None values
        - Common insecure patterns (case-insensitive)
        - Values shorter than 32 characters
        - Known insecure default strings
    """
    if not value:
        return True

    value_lower = value.lower()

    # Check for known insecure patterns (all patterns are already lowercase)
    for pattern in INSECURE_DEFAULTS:
        if pattern in value_lower:
            return True

    # Check for obviously weak secrets (too short)
    if len(value) < 32:
        return True

    # Check for common weak patterns (single words)
    return value_lower in {"secret", "password", "admin", "12345678"}


def validate_secret_security(value: str, name: str) -> tuple[bool, str]:
    """
    Validate that a secret meets security requirements.

    Args:
        value: The secret value to validate
        name: Name of the secret (for error messages)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value:
        return False, f"{name} is not set"

    if is_insecure_default(value):
        return False, (
            f"{name} appears to be an insecure default\n"
            f"   Current value: {value[:20]}...\n"
            f"   Action: Generate a secure random value using "
            f"`python scripts/generate_secrets.py`"
        )

    if len(value) < 32:
        return False, f"{name} is too short (minimum 32 characters)"

    return True, ""
