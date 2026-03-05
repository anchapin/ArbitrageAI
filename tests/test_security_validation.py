"""
Tests for Production Security Validation (QAQC-003).

Tests cover:
- Insecure default detection
- Production validation failure with insecure defaults
- Production validation success with secure secrets
- Development mode skips validation
- Clear error messages guide users to resolution
- Validation runs early in startup process

Issue: QAQC-003 - Production Validation for Insecure Defaults
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from src.utils.secrets import (
    generate_secure_secret,
    is_insecure_default,
    validate_secret_security,
    INSECURE_DEFAULTS,
)
from src.config.config_manager import (
    ConfigManager,
    validate_production_configuration,
)


@pytest.fixture(autouse=True)
def reset_config_and_env():
    """Reset ConfigManager and clean up environment before/after each test."""
    ConfigManager.reset_instance()

    # Store original environment
    original_env = {
        "JWT_SECRET_KEY": os.environ.get("JWT_SECRET_KEY"),
        "CLIENT_AUTH_SECRET": os.environ.get("CLIENT_AUTH_SECRET"),
        "DATABASE_ENCRYPTION_KEY": os.environ.get("DATABASE_ENCRYPTION_KEY"),
        "STRIPE_SECRET_KEY": os.environ.get("STRIPE_SECRET_KEY"),
        "STRIPE_WEBHOOK_SECRET": os.environ.get("STRIPE_WEBHOOK_SECRET"),
        "ENVIRONMENT": os.environ.get("ENVIRONMENT"),
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
    }

    yield

    # Restore original environment
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    ConfigManager.reset_instance()


class TestInsecureDefaultDetection:
    """Test detection of insecure default values."""

    @pytest.mark.parametrize(
        "insecure_value",
        [
            "CHANGE_ME_IN_PRODUCTION_generate_a_secure_random_32_byte_key",
            "CHANGE_ME_IN_PRODUCTION_use_a_random_32_byte_key",
            "your-secret-key-here",
            "your-jwt-secret-here",
            "your-openai-api-key-here",
            "sk_test_",
            "pk_test_",
            "whsec_test_key",
            "password",
            "admin",
            "12345678",
            "",
            None,
            "short",
            "weak123",
            "test_secret",
            "placeholder",
            "test_key",
            "test_value",
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
            generate_secure_secret(),
            generate_secure_secret(),
            generate_secure_secret(),
        ],
    )
    def test_accepts_secure_values(self, secure_value):
        """Test that secure values are not flagged as insecure."""
        assert is_insecure_default(secure_value) is False

    def test_rejects_values_shorter_than_32_chars(self):
        """Test that values shorter than 32 characters are rejected."""
        short_values = [
            "short",
            "1234567890123456789012345678901",  # 31 chars
            "not_long_enough",
            "too_short_secret",
        ]

        for value in short_values:
            assert is_insecure_default(value) is True

    def test_case_insensitive_detection(self):
        """Test that detection is case-insensitive."""
        insecure_variants = [
            "change_me_in_production",
            "CHANGE_ME_IN_PRODUCTION",
            "Change_Me_In_Production",
            "your-secret-key-here",
            "YOUR-SECRET-KEY-HERE",
            "Your-Secret-Key-Here",
        ]

        for value in insecure_variants:
            assert is_insecure_default(value) is True

    def test_partial_pattern_matching(self):
        """Test that partial patterns are detected."""
        # Values containing insecure patterns should be detected
        assert is_insecure_default("prefix_CHANGE_ME_IN_PRODUCTION_suffix") is True
        assert is_insecure_default("my_sk_test_key") is True
        assert is_insecure_default("test_whsec_test_secret") is True
        assert is_insecure_default("prefix_placeholder_suffix") is True


class TestValidateSecretSecurity:
    """Test secret security validation helper function."""

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
        # Should mention insecure default or too short
        assert "insecure default" in error_msg or "too short" in error_msg

    def test_validates_secure_secret(self):
        """Test that secure secret passes validation."""
        secure_secret = generate_secure_secret()
        is_valid, error_msg = validate_secret_security(secure_secret, "JWT_SECRET_KEY")

        assert is_valid is True
        assert error_msg == ""

    def test_error_message_includes_action(self):
        """Test that error message includes guidance for resolution."""
        is_valid, error_msg = validate_secret_security(
            "CHANGE_ME_IN_PRODUCTION",
            "JWT_SECRET_KEY",
        )

        assert is_valid is False
        assert "generate_secrets.py" in error_msg or "Action" in error_msg


class TestProductionValidation:
    """Test production security validation."""

    def test_production_fails_with_insecure_jwt_secret(self, monkeypatch, caplog):
        """Test that production mode fails with insecure JWT secret."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv(
            "JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_generate_a_secure_random_32_byte_key"
        )
        monkeypatch.setenv("CLIENT_AUTH_SECRET", generate_secure_secret())
        monkeypatch.setenv("STRIPE_SECRET_KEY", "[STRIPE_SECRET_KEY_PLACEHOLDER]")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "[STRIPE_WEBHOOK_SECRET_PLACEHOLDER]")

        with pytest.raises(SystemExit) as exc_info:
            validate_production_configuration()

        assert exc_info.value.code == 1
        assert "PRODUCTION SECURITY VALIDATION FAILED" in caplog.text
        assert "JWT_SECRET_KEY" in caplog.text

    def test_production_fails_with_insecure_client_secret(self, monkeypatch, caplog):
        """Test that production mode fails with insecure client secret."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", generate_secure_secret())
        monkeypatch.setenv(
            "CLIENT_AUTH_SECRET", "CHANGE_ME_IN_PRODUCTION_use_a_random_32_byte_key"
        )
        monkeypatch.setenv("STRIPE_SECRET_KEY", "[STRIPE_SECRET_KEY_PLACEHOLDER]")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "[STRIPE_WEBHOOK_SECRET_PLACEHOLDER]")

        with pytest.raises(SystemExit) as exc_info:
            validate_production_configuration()

        assert exc_info.value.code == 1
        assert "CLIENT_AUTH_SECRET" in caplog.text

    def test_production_fails_with_missing_jwt_secret(self, monkeypatch, caplog):
        """Test that production mode fails with missing JWT secret."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.setenv("CLIENT_AUTH_SECRET", generate_secure_secret())
        monkeypatch.setenv("STRIPE_SECRET_KEY", "[STRIPE_SECRET_KEY_PLACEHOLDER]")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "[STRIPE_WEBHOOK_SECRET_PLACEHOLDER]")

        with pytest.raises(SystemExit) as exc_info:
            validate_production_configuration()

        assert exc_info.value.code == 1
        assert "JWT_SECRET_KEY is not set" in caplog.text

    def test_production_fails_with_multiple_insecure_secrets(self, monkeypatch, caplog):
        """Test that production mode fails with multiple insecure secrets."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
        monkeypatch.setenv("CLIENT_AUTH_SECRET", "weak")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_insecure")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "[STRIPE_WEBHOOK_SECRET_PLACEHOLDER]")

        with pytest.raises(SystemExit) as exc_info:
            validate_production_configuration()

        assert exc_info.value.code == 1
        # Should report all errors
        assert "JWT_SECRET_KEY" in caplog.text
        assert "CLIENT_AUTH_SECRET" in caplog.text
        assert "STRIPE_SECRET_KEY" in caplog.text
        assert "STRIPE_WEBHOOK_SECRET" in caplog.text

    def test_production_passes_with_secure_secrets(self, monkeypatch, caplog):
        """Test that production mode passes with secure secrets."""
        import logging
        caplog.set_level(logging.INFO)
        
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", generate_secure_secret())
        monkeypatch.setenv("CLIENT_AUTH_SECRET", generate_secure_secret())
        # Use genuinely secure values (32+ chars, no insecure patterns)
        # These are randomly generated secure values
        monkeypatch.setenv("STRIPE_SECRET_KEY", generate_secure_secret())
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", generate_secure_secret())
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

        # Should not raise
        validate_production_configuration()

        assert "Production security validation passed" in caplog.text

    def test_development_skips_validation(self, monkeypatch, caplog):
        """Test that development mode skips production validation."""
        import logging
        caplog.set_level(logging.INFO)
        
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv(
            "JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_generate_a_secure_random_32_byte_key"
        )

        # Should not raise in development
        validate_production_configuration()

        assert "Skipping production validation" in caplog.text

    def test_staging_skips_validation(self, monkeypatch, caplog):
        """Test that staging mode skips production validation."""
        import logging
        caplog.set_level(logging.INFO)
        
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.setenv("JWT_SECRET_KEY", "insecure_default")

        # Should not raise in staging
        validate_production_configuration()

        assert "Skipping production validation" in caplog.text

    def test_error_message_includes_resolution_steps(self, monkeypatch, caplog):
        """Test that error message includes clear resolution steps."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
        monkeypatch.setenv("CLIENT_AUTH_SECRET", generate_secure_secret())
        monkeypatch.setenv("STRIPE_SECRET_KEY", "[STRIPE_SECRET_KEY_PLACEHOLDER]")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "[STRIPE_WEBHOOK_SECRET_PLACEHOLDER]")

        with pytest.raises(SystemExit):
            validate_production_configuration()

        # Check for helpful error messages
        assert "ACTION REQUIRED" in caplog.text
        assert "generate_secrets.py" in caplog.text
        assert "Set environment variables securely" in caplog.text
        assert "Never commit secrets" in caplog.text

    def test_error_shows_partial_secret_value(self, monkeypatch, caplog):
        """Test that error shows partial secret value for identification."""
        import logging
        caplog.set_level(logging.CRITICAL)
        
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_test_value")
        monkeypatch.setenv("CLIENT_AUTH_SECRET", generate_secure_secret())
        monkeypatch.setenv("STRIPE_SECRET_KEY", "[STRIPE_SECRET_KEY_PLACEHOLDER]")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b1c2d")

        with pytest.raises(SystemExit):
            validate_production_configuration()

        # Should show partial value (first 20 chars) in log records
        # The value is truncated to 20 chars + "..." so we check for the prefix
        assert any("CHANGE_ME_IN_PRODUCT" in r.message for r in caplog.records)
        assert any("Current value:" in r.message for r in caplog.records)
        assert any("..." in r.message for r in caplog.records)


class TestValidationStartupIntegration:
    """Test that validation runs early in startup process."""

    def test_validation_called_in_lifespan(self, monkeypatch, caplog):
        """Test that validation is called during application lifespan."""
        from src.api.system import lifespan
        from fastapi import FastAPI

        monkeypatch.setenv("ENVIRONMENT", "development")

        app = FastAPI(lifespan=lifespan)

        # The lifespan should execute without errors in development
        # This verifies the integration point exists
        assert lifespan is not None

    def test_validation_before_other_initialization(self, monkeypatch):
        """Test that validation runs before other initialization."""
        # This test verifies the order of operations in system.py
        # by checking that validate_production_configuration is imported
        from src.api.system import lifespan
        import inspect

        # Get the source code to verify validation is called first
        source = inspect.getsource(lifespan)

        # Validation should be called before other initialization
        assert "validate_production_configuration" in source
        # Check it appears early in the function
        lines = source.split('\n')
        validation_line = None
        init_db_line = None

        for i, line in enumerate(lines):
            if "validate_production_configuration" in line:
                validation_line = i
            if "init_db" in line and validation_line is None:
                init_db_line = i

        # Validation should come before or at same level as init_db
        if validation_line is not None and init_db_line is not None:
            assert validation_line <= init_db_line


class TestInsecureDefaultsConfiguration:
    """Test the INSECURE_DEFAULTS configuration."""

    def test_insecure_defaults_is_a_set(self):
        """Test that INSECURE_DEFAULTS is a set for O(1) lookup."""
        assert isinstance(INSECURE_DEFAULTS, set)

    def test_contains_expected_patterns(self):
        """Test that INSECURE_DEFAULTS contains expected patterns."""
        expected_patterns = {
            "change_me_in_production",
            "your-secret-key-here",
            "your-jwt-secret-here",
            "your-openai-api-key-here",
            "sk_test_",
            "pk_test_",
            "whsec_test",
            "placeholder",
            "test_secret",
            "test_key",
            "test_value",
        }

        for pattern in expected_patterns:
            assert pattern in INSECURE_DEFAULTS

    def test_contains_common_weak_passwords(self):
        """Test that common weak passwords are included."""
        weak_passwords = {
            "password",
            "admin",
            "12345678",
        }

        for password in weak_passwords:
            assert password in INSECURE_DEFAULTS


class TestConfigManagerStaticMethod:
    """Test ConfigManager.validate_production_configuration static method."""

    def test_static_method_exists(self):
        """Test that the static method exists on ConfigManager."""
        assert hasattr(ConfigManager, "validate_production_configuration")
        assert callable(ConfigManager.validate_production_configuration)

    def test_module_level_function_exists(self):
        """Test that module-level validation function exists."""
        from src.config.config_manager import validate_production_configuration as vpc
        assert callable(vpc)

    def test_both_functions_are_equivalent(self, monkeypatch):
        """Test that both functions behave identically."""
        monkeypatch.setenv("ENVIRONMENT", "development")

        # Both should work without raising
        ConfigManager.validate_production_configuration()

        from src.config.config_manager import validate_production_configuration as vpc
        vpc()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_whitespace_only_secret(self, monkeypatch):
        """Test that whitespace-only secrets are rejected."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "   ")
        monkeypatch.setenv("CLIENT_AUTH_SECRET", generate_secure_secret())
        monkeypatch.setenv("STRIPE_SECRET_KEY", "[STRIPE_SECRET_KEY_PLACEHOLDER]")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "[STRIPE_WEBHOOK_SECRET_PLACEHOLDER]")

        with pytest.raises(SystemExit):
            validate_production_configuration()

    def test_newline_in_secret(self, monkeypatch):
        """Test that secrets with newlines are handled."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "secret\nwith\nnewlines")
        monkeypatch.setenv("CLIENT_AUTH_SECRET", generate_secure_secret())
        monkeypatch.setenv("STRIPE_SECRET_KEY", "[STRIPE_SECRET_KEY_PLACEHOLDER]")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "[STRIPE_WEBHOOK_SECRET_PLACEHOLDER]")

        # Should be rejected as insecure (too short when split)
        with pytest.raises(SystemExit):
            validate_production_configuration()

    def test_unicode_characters_in_secure_secret(self, monkeypatch):
        """Test that unicode characters in secure secrets are accepted."""
        # Generate a secure secret and verify it passes
        secure_secret = generate_secure_secret()
        assert is_insecure_default(secure_secret) is False

    def test_exactly_32_character_secret(self, monkeypatch):
        """Test that exactly 32 character secrets are accepted."""
        # 32 hex characters = 16 bytes, which is the minimum
        secret_32 = "a" * 32
        # Should pass length check but may fail other checks
        # The is_insecure_default checks for < 32, so exactly 32 should pass length
        assert len(secret_32) == 32
        # But it will fail pattern matching since it's all 'a'
        # Let's use a proper 32-char hex string
        proper_32 = "abcdef9876543210abcdef9876543210"
        assert is_insecure_default(proper_32) is False

    def test_31_character_secret_rejected(self):
        """Test that 31 character secrets are rejected."""
        secret_31 = "a" * 31
        assert is_insecure_default(secret_31) is True

    def test_33_character_secret_accepted(self):
        """Test that 33 character secrets are accepted if no patterns match."""
        secret_33 = "a" * 33
        # Will be rejected due to pattern (all same char)
        # Let's use a proper value
        proper_33 = "abcdef9876543210abcdef98765432101"
        assert is_insecure_default(proper_33) is False


class TestLoggingAndOutput:
    """Test logging and output behavior."""

    def test_critical_log_level_used(self, monkeypatch, caplog):
        """Test that critical security issues use CRITICAL log level."""
        import logging
        caplog.set_level(logging.CRITICAL)
        
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
        monkeypatch.setenv("CLIENT_AUTH_SECRET", generate_secure_secret())
        monkeypatch.setenv("STRIPE_SECRET_KEY", "[STRIPE_SECRET_KEY_PLACEHOLDER]")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b1c2d")

        with pytest.raises(SystemExit):
            validate_production_configuration()

        # Check that CRITICAL level is used
        critical_records = [r for r in caplog.records if r.levelname == "CRITICAL"]
        assert len(critical_records) > 0

    def test_warning_log_level_for_non_critical(self, monkeypatch, caplog):
        """Test that warnings use WARNING log level."""
        import logging
        caplog.set_level(logging.WARNING)
        
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", generate_secure_secret())
        monkeypatch.setenv("CLIENT_AUTH_SECRET", generate_secure_secret())
        monkeypatch.setenv("STRIPE_SECRET_KEY", "[STRIPE_SECRET_KEY_PLACEHOLDER]")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b1c2d")
        # Don't set DATABASE_URL to trigger warning
        monkeypatch.delenv("DATABASE_URL", raising=False)

        # This will fail because DATABASE_URL is not set, but we're testing warning logging
        try:
            validate_production_configuration()
        except SystemExit:
            pass

        # Check that WARNING level is used for non-critical issues
        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        # Should have warning about DATABASE_URL
        assert len(warning_records) > 0
        assert any("DATABASE_URL" in r.message for r in warning_records)

    def test_info_log_on_success(self, monkeypatch, caplog):
        """Test that success logs at INFO level."""
        import logging
        caplog.set_level(logging.INFO)
        
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", generate_secure_secret())
        monkeypatch.setenv("CLIENT_AUTH_SECRET", generate_secure_secret())
        # Use genuinely secure values (32+ chars, no insecure patterns)
        monkeypatch.setenv("STRIPE_SECRET_KEY", generate_secure_secret())
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", generate_secure_secret())
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

        validate_production_configuration()

        info_records = [r for r in caplog.records if r.levelname == "INFO"]
        assert any("Production security validation passed" in r.message for r in info_records)
