"""
Tests for Secure Secret Management Module.

Tests cover:
- Secure secret generation
- Secret file persistence with correct permissions
- Auto-generation on first startup
- Insecure default detection
- Production validation
- Integration with configuration manager

Issue: QAQC-002 - Secure Random Secret Generation
"""

import json
import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.utils.secrets import (
    SECRETS_FILE,
    INSECURE_DEFAULTS,
    generate_secure_secret,
    _load_secrets,
    _save_secrets,
    load_or_create_secrets,
    is_insecure_default,
    validate_secret_security,
)
from src.config.config_manager import ConfigManager


@pytest.fixture(autouse=True)
def reset_config_and_env():
    """Reset ConfigManager and clean up environment before/after each test."""
    ConfigManager.reset_instance()

    # Store original environment
    original_env = {
        "JWT_SECRET_KEY": os.environ.get("JWT_SECRET_KEY"),
        "CLIENT_AUTH_SECRET": os.environ.get("CLIENT_AUTH_SECRET"),
        "DATABASE_ENCRYPTION_KEY": os.environ.get("DATABASE_ENCRYPTION_KEY"),
        "ENVIRONMENT": os.environ.get("ENVIRONMENT"),
    }

    yield

    # Restore original environment
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    ConfigManager.reset_instance()


@pytest.fixture
def temp_secrets_file(tmp_path):
    """Create a temporary secrets file for testing."""
    secrets_file = tmp_path / ".secrets"
    original_secrets_file = SECRETS_FILE

    # Patch SECRETS_FILE to use temp location
    with patch.object(
        type(SECRETS_FILE),
        "__new__",
        return_value=secrets_file,
    ):
        yield secrets_file


class TestGenerateSecureSecret:
    """Test secure secret generation."""

    def test_generates_256_bit_secret(self):
        """Test that generated secret is 256-bit (64 hex characters)."""
        secret = generate_secure_secret()

        assert len(secret) == 64  # 32 bytes = 64 hex characters

    def test_generates_hex_string(self):
        """Test that generated secret is valid hex string."""
        secret = generate_secure_secret()

        # Should only contain hex characters
        assert all(c in "0123456789abcdef" for c in secret.lower())

    def test_generates_unique_secrets(self):
        """Test that each generated secret is unique."""
        secrets = [generate_secure_secret() for _ in range(100)]

        # All secrets should be unique
        assert len(set(secrets)) == 100

    def test_cryptographically_secure(self):
        """Test that secrets use cryptographically secure random generation."""
        # Generate multiple secrets and check for randomness
        secrets = [generate_secure_secret() for _ in range(10)]

        # Check that secrets don't have obvious patterns
        for secret in secrets:
            # Should not be all same character
            assert len(set(secret)) > 10
            # Should not be sequential
            assert secret not in "0123456789abcdef" * 4


class TestSaveAndLoadSecrets:
    """Test secret file persistence."""

    def test_save_secrets_creates_file(self, tmp_path):
        """Test that saving secrets creates the file."""
        secrets_file = tmp_path / ".secrets"

        with patch("src.utils.secrets.SECRETS_FILE", secrets_file):
            test_secrets = {
                "JWT_SECRET_KEY": "test_secret_1",
                "CLIENT_AUTH_SECRET": "test_secret_2",
            }

            _save_secrets(test_secrets)

            assert secrets_file.exists()

    def test_save_secrets_sets_secure_permissions(self, tmp_path):
        """Test that saved secrets have secure permissions (0o600)."""
        secrets_file = tmp_path / ".secrets"

        with patch("src.utils.secrets.SECRETS_FILE", secrets_file):
            test_secrets = {"JWT_SECRET_KEY": "test_secret"}

            _save_secrets(test_secrets)

            # Check file permissions
            file_mode = secrets_file.stat().st_mode & 0o777
            assert file_mode == 0o600

    def test_save_secrets_creates_parent_directory(self, tmp_path):
        """Test that saving secrets creates parent directories if needed."""
        secrets_file = tmp_path / "nested" / "dir" / ".secrets"

        with patch("src.utils.secrets.SECRETS_FILE", secrets_file):
            test_secrets = {"JWT_SECRET_KEY": "test_secret"}

            _save_secrets(test_secrets)

            assert secrets_file.exists()
            assert secrets_file.parent.exists()

    def test_load_secrets_reads_file(self, tmp_path):
        """Test that loading secrets reads from file correctly."""
        secrets_file = tmp_path / ".secrets"

        test_secrets = {
            "JWT_SECRET_KEY": "test_jwt_secret",
            "CLIENT_AUTH_SECRET": "test_client_secret",
        }

        # Write secrets manually
        secrets_file.write_text(json.dumps(test_secrets, indent=2))
        secrets_file.chmod(0o600)

        with patch("src.utils.secrets.SECRETS_FILE", secrets_file):
            loaded = _load_secrets()

            assert loaded == test_secrets

    def test_load_secrets_fixes_insecure_permissions(self, tmp_path):
        """Test that loading secrets fixes insecure file permissions."""
        secrets_file = tmp_path / ".secrets"

        test_secrets = {"JWT_SECRET_KEY": "test_secret"}

        # Write secrets with insecure permissions
        secrets_file.write_text(json.dumps(test_secrets, indent=2))
        secrets_file.chmod(0o644)  # Insecure: world-readable

        with patch("src.utils.secrets.SECRETS_FILE", secrets_file):
            loaded = _load_secrets()

            # Should have fixed permissions
            file_mode = secrets_file.stat().st_mode & 0o777
            assert file_mode == 0o600

    def test_load_secrets_file_not_found(self, tmp_path):
        """Test that loading non-existent file raises FileNotFoundError."""
        secrets_file = tmp_path / ".secrets"

        with patch("src.utils.secrets.SECRETS_FILE", secrets_file):
            with pytest.raises(FileNotFoundError):
                _load_secrets()


class TestLoadOrCreateSecrets:
    """Test auto-generation of secrets on first startup."""

    def test_loads_existing_secrets(self, tmp_path):
        """Test that existing secrets are loaded."""
        secrets_file = tmp_path / ".secrets"

        existing_secrets = {
            "JWT_SECRET_KEY": "existing_jwt",
            "CLIENT_AUTH_SECRET": "existing_client",
        }

        secrets_file.write_text(json.dumps(existing_secrets, indent=2))
        secrets_file.chmod(0o600)

        with patch("src.utils.secrets.SECRETS_FILE", secrets_file):
            loaded = load_or_create_secrets()

            assert loaded == existing_secrets

    def test_creates_new_secrets_if_not_exist(self, tmp_path):
        """Test that new secrets are created if file doesn't exist."""
        secrets_file = tmp_path / ".secrets"

        with patch("src.utils.secrets.SECRETS_FILE", secrets_file):
            created = load_or_create_secrets()

            # Check file was created
            assert secrets_file.exists()

            # Check required secrets exist
            assert "JWT_SECRET_KEY" in created
            assert "CLIENT_AUTH_SECRET" in created
            assert "DATABASE_ENCRYPTION_KEY" in created

            # Check secrets are secure (64 hex chars)
            for key, value in created.items():
                assert len(value) == 64
                assert all(c in "0123456789abcdef" for c in value.lower())

    def test_created_secrets_are_persisted(self, tmp_path):
        """Test that created secrets are saved to file."""
        secrets_file = tmp_path / ".secrets"

        with patch("src.utils.secrets.SECRETS_FILE", secrets_file):
            created = load_or_create_secrets()

            # Load again to verify persistence
            loaded = load_or_create_secrets()

            assert created == loaded


class TestIsInsecureDefault:
    """Test insecure default detection."""

    @pytest.mark.parametrize(
        "insecure_value",
        [
            "CHANGE_ME_IN_PRODUCTION_generate_a_secure_random_32_byte_key",
            "CHANGE_ME_IN_PRODUCTION_use_a_random_32_byte_key",
            "your-secret-key-here",
            "your-jwt-secret-here",
            "sk_test_",
            "pk_test_",
            "whsec_test",
            "password",
            "admin",
            "12345678",
            "",
            None,
        ],
    )
    def test_detects_known_insecure_defaults(self, insecure_value):
        """Test that known insecure defaults are detected."""
        if insecure_value is None:
            assert is_insecure_default("") is True
        else:
            assert is_insecure_default(insecure_value) is True

    @pytest.mark.parametrize(
        "secure_value",
        [
            "a" * 64,  # 64 character hex string
            "f" * 64,
            "abcdef9876543210abcdef9876543210abcdef9876543210abcdef98765432",
            "deadbeefcafe9876543210abcdef9876deadbeefcafe9876543210abcdef9876",
        ],
    )
    def test_accepts_secure_values(self, secure_value):
        """Test that secure values are not flagged as insecure."""
        assert is_insecure_default(secure_value) is False

    def test_rejects_short_values(self):
        """Test that values shorter than 32 characters are rejected."""
        short_values = [
            "short",
            "1234567890123456789012345678901",  # 31 chars
            "not_long_enough",
        ]

        for value in short_values:
            assert is_insecure_default(value) is True


class TestValidateSecretSecurity:
    """Test secret security validation."""

    def test_validates_empty_secret(self):
        """Test that empty secret fails validation."""
        is_valid, error_msg = validate_secret_security("", "JWT_SECRET_KEY")

        assert is_valid is False
        assert "not set" in error_msg

    def test_validates_insecure_default(self):
        """Test that insecure default fails validation."""
        is_valid, error_msg = validate_secret_security(
            "CHANGE_ME_IN_PRODUCTION_generate_a_secure_random_32_byte_key",
            "JWT_SECRET_KEY",
        )

        assert is_valid is False
        assert "insecure default" in error_msg

    def test_validates_short_secret(self):
        """Test that short secret fails validation."""
        is_valid, error_msg = validate_secret_security("short", "JWT_SECRET_KEY")

        assert is_valid is False
        assert "insecure default" in error_msg or "too short" in error_msg

    def test_validates_secure_secret(self):
        """Test that secure secret passes validation."""
        secure_secret = generate_secure_secret()
        is_valid, error_msg = validate_secret_security(secure_secret, "JWT_SECRET_KEY")

        assert is_valid is True
        assert error_msg == ""


class TestConfigManagerIntegration:
    """Test integration with ConfigManager."""

    def test_config_loads_secrets_automatically(self, tmp_path):
        """Test that ConfigManager loads secrets on initialization."""
        secrets_file = tmp_path / ".secrets"

        test_secrets = {
            "JWT_SECRET_KEY": generate_secure_secret(),
            "CLIENT_AUTH_SECRET": generate_secure_secret(),
        }

        secrets_file.write_text(json.dumps(test_secrets, indent=2))
        secrets_file.chmod(0o600)

        # Clear environment variables before test
        os.environ.pop("JWT_SECRET_KEY", None)
        os.environ.pop("CLIENT_AUTH_SECRET", None)

        with patch("src.utils.secrets.SECRETS_FILE", secrets_file):
            config = ConfigManager.get_instance()

            # Verify secrets were loaded into environment
            assert os.environ.get("JWT_SECRET_KEY") == test_secrets["JWT_SECRET_KEY"]
            assert (
                os.environ.get("CLIENT_AUTH_SECRET")
                == test_secrets["CLIENT_AUTH_SECRET"]
            )

    def test_config_uses_environment_override(self, tmp_path, monkeypatch):
        """Test that environment variables override file secrets."""
        secrets_file = tmp_path / ".secrets"

        test_secrets = {
            "JWT_SECRET_KEY": "file_secret",
            "CLIENT_AUTH_SECRET": "file_secret",
        }

        secrets_file.write_text(json.dumps(test_secrets, indent=2))
        secrets_file.chmod(0o600)

        # Set environment override
        monkeypatch.setenv("JWT_SECRET_KEY", "env_override_secret_1234567890abcdef")

        with patch("src.utils.secrets.SECRETS_FILE", secrets_file):
            config = ConfigManager.get_instance()

            # Environment should take priority
            assert (
                os.environ.get("JWT_SECRET_KEY") == "env_override_secret_1234567890abcdef"
            )


class TestProductionValidation:
    """Test production security validation."""

    def test_production_fails_with_insecure_jwt_secret(self, monkeypatch):
        """Test that production mode fails with insecure JWT secret."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv(
            "JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_generate_a_secure_random_32_byte_key"
        )
        monkeypatch.setenv("CLIENT_AUTH_SECRET", generate_secure_secret())
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_secure")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_secure")

        with pytest.raises(SystemExit) as exc_info:
            ConfigManager.validate_production_configuration()

        assert exc_info.value.code == 1

    def test_production_fails_with_insecure_client_secret(self, monkeypatch):
        """Test that production mode fails with insecure client secret."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", generate_secure_secret())
        monkeypatch.setenv(
            "CLIENT_AUTH_SECRET", "CHANGE_ME_IN_PRODUCTION_use_a_random_32_byte_key"
        )
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_secure")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_secure")

        with pytest.raises(SystemExit) as exc_info:
            ConfigManager.validate_production_configuration()

        assert exc_info.value.code == 1

    def test_production_passes_with_secure_secrets(self, monkeypatch):
        """Test that production mode passes with secure secrets."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", generate_secure_secret())
        monkeypatch.setenv("CLIENT_AUTH_SECRET", generate_secure_secret())
        # Use secure placeholder values (not real Stripe keys)
        monkeypatch.setenv("STRIPE_SECRET_KEY", "[STRIPE_SECRET_KEY_PLACEHOLDER_32chars]")
        # Webhook secret should be a secure random value
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "[STRIPE_WEBHOOK_SECRET_PLACEHOLDER_40chars]")

        # Should not raise
        ConfigManager.validate_production_configuration()

    def test_development_skips_validation(self, monkeypatch):
        """Test that development mode skips production validation."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv(
            "JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_generate_a_secure_random_32_byte_key"
        )

        # Should not raise in development
        ConfigManager.validate_production_configuration()


class TestSecretFilePermissions:
    """Test secret file permission security."""

    def test_permissions_are_owner_read_write_only(self, tmp_path):
        """Test that secrets file has owner read/write only permissions."""
        secrets_file = tmp_path / ".secrets"

        test_secrets = {"JWT_SECRET_KEY": generate_secure_secret()}

        with patch("src.utils.secrets.SECRETS_FILE", secrets_file):
            _save_secrets(test_secrets)

            # Check permissions
            file_stat = secrets_file.stat()
            assert file_stat.st_mode & stat.S_IRUSR  # Owner read
            assert file_stat.st_mode & stat.S_IWUSR  # Owner write
            assert not (file_stat.st_mode & stat.S_IRGRP)  # Group read
            assert not (file_stat.st_mode & stat.S_IWGRP)  # Group write
            assert not (file_stat.st_mode & stat.S_IROTH)  # Other read
            assert not (file_stat.st_mode & stat.S_IWOTH)  # Other write

    def test_permissions_format(self, tmp_path):
        """Test that permissions are exactly 0o600."""
        secrets_file = tmp_path / ".secrets"

        test_secrets = {"JWT_SECRET_KEY": generate_secure_secret()}

        with patch("src.utils.secrets.SECRETS_FILE", secrets_file):
            _save_secrets(test_secrets)

            file_mode = secrets_file.stat().st_mode & 0o777
            assert file_mode == 0o600


class TestInsecureDefaultsSet:
    """Test the INSECURE_DEFAULTS set."""

    def test_contains_known_insecure_patterns(self):
        """Test that INSECURE_DEFAULTS contains expected patterns."""
        expected_patterns = {
            "change_me_in_production",
            "your-secret-key-here",
            "your-jwt-secret-here",
        }

        for pattern in expected_patterns:
            assert pattern in INSECURE_DEFAULTS

    def test_is_a_set(self):
        """Test that INSECURE_DEFAULTS is a set for O(1) lookup."""
        assert isinstance(INSECURE_DEFAULTS, set)


class TestSecretGenerationScript:
    """Test the generate_secrets.py script functionality."""

    def test_script_generates_required_secrets(self, tmp_path):
        """Test that script generates all required secrets."""
        secrets_file = tmp_path / ".secrets"

        # Import and patch
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

        with patch("scripts.generate_secrets.SECRETS_FILE", secrets_file):
            from scripts.generate_secrets import generate_secure_secret, main
            import io
            from contextlib import redirect_stdout

            # Capture output
            f = io.StringIO()
            with redirect_stdout(f):
                # Simulate 'y' response for overwrite prompt
                with patch("builtins.input", return_value="y"):
                    main()

            # Check file was created
            assert secrets_file.exists()

            # Check secrets were generated
            with open(secrets_file) as f:
                secrets = json.load(f)

            assert "JWT_SECRET_KEY" in secrets
            assert "CLIENT_AUTH_SECRET" in secrets
            assert "DATABASE_ENCRYPTION_KEY" in secrets

            # Check secrets are secure
            for key, value in secrets.items():
                assert len(value) == 64
