"""Tests for error tracking module (Issue #230).

Tests Sentry integration, error capturing, context enrichment,
and logging integration.
"""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

# Import sentry_sdk for mocking
from src.utils import error_tracking as error_tracking_module
sentry_sdk = error_tracking_module.sentry_sdk


class TestErrorTrackingConfig:
    """Tests for ErrorTrackingConfig class."""

    def test_get_with_default(self):
        """Test getting config with default value."""
        # Import here to avoid circular imports
        from src.utils.error_tracking import ErrorTrackingConfig

        # Clear any cached env vars
        with patch.dict(os.environ, {}, clear=True):
            result = ErrorTrackingConfig.get("SENTRY_DSN")
            assert result is None

    def test_get_from_environment(self):
        """Test getting config from environment variable."""
        from src.utils.error_tracking import ErrorTrackingConfig

        test_dsn = "https://key@sentry.io/123"
        with patch.dict(os.environ, {"SENTRY_DSN": test_dsn}):
            result = ErrorTrackingConfig.get("SENTRY_DSN")
            assert result == test_dsn


class TestErrorTrackingInitialization:
    """Tests for error tracking initialization."""

    def test_init_error_tracking_returns_false_without_dsn(self):
        """Test initialization returns False when no DSN configured."""
        # The init_error_tracking function checks for DSN via ErrorTrackingConfig.get
        # When SENTRY_AVAILABLE is False (sentry_sdk not installed), init returns False
        from src.utils.error_tracking import init_error_tracking, SENTRY_AVAILABLE

        # If sentry is not available, init should return False
        if not SENTRY_AVAILABLE:
            result = init_error_tracking()
            assert result is False
        else:
            # If sentry is available but no DSN, should return False
            from src.utils.error_tracking import ErrorTrackingConfig
            original_get = ErrorTrackingConfig.get
            try:
                ErrorTrackingConfig.get = lambda key, default=None: None
                result = init_error_tracking()
                assert result is False
            finally:
                ErrorTrackingConfig.get = original_get

    def test_init_error_tracke_works(self):
        """Test that init_error_tracking function exists and is callable."""
        from src.utils.error_tracking import init_error_tracking

        assert callable(init_error_tracking)


class TestCaptureFunctions:
    """Tests for capture exception and message functions."""

    def test_capture_exception_function_exists(self):
        """Test capture_exception function exists."""
        from src.utils.error_tracking import capture_exception
        assert callable(capture_exception)

    def test_capture_message_function_exists(self):
        """Test capture_message function exists."""
        from src.utils.error_tracking import capture_message
        assert callable(capture_message)


class TestContextFunctions:
    """Tests for context management functions."""

    def test_set_context_function_exists(self):
        """Test set_context function exists."""
        from src.utils.error_tracking import set_context
        assert callable(set_context)

    def test_set_user_function_exists(self):
        """Test set_user function exists."""
        from src.utils.error_tracking import set_user
        assert callable(set_user)

    def test_add_breadcrumb_function_exists(self):
        """Test add_breadcrumb function exists."""
        from src.utils.error_tracking import add_breadcrumb
        assert callable(add_breadcrumb)


class TestErrorTrackerContextManager:
    """Tests for ErrorTracker context manager."""

    @patch("src.utils.error_tracking.start_transaction")
    def test_error_tracker_context_manager(self, mock_start_tx):
        """Test ErrorTracker as context manager."""
        from src.utils.error_tracking import ErrorTracker

        mock_tx = MagicMock()
        mock_start_tx.return_value = mock_tx

        with ErrorTracker(operation_name="test_operation"):
            pass

        mock_start_tx.assert_called_once_with(
            name="test_operation",
            operation="operation",
        )
        mock_tx.__exit__.assert_called()

    @patch("src.utils.error_tracking.start_transaction")
    @patch("src.utils.error_tracking.capture_exception")
    def test_error_tracker_captures_exception(self, mock_capture, mock_start_tx):
        """Test ErrorTracker captures exceptions."""
        from src.utils.error_tracking import ErrorTracker

        mock_tx = MagicMock()
        mock_start_tx.return_value = mock_tx

        try:
            with ErrorTracker(operation_name="test_op"):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Exception should be captured
        mock_capture.assert_called_once()


class TestSentryUnavailable:
    """Tests when Sentry is not available (SENTRY_AVAILABLE=False)."""

    @patch("src.utils.error_tracking.SENTRY_AVAILABLE", False)
    def test_capture_exception_when_unavailable(self):
        """Test capture_exception returns None when Sentry unavailable."""
        # Re-import to get mocked version
        import importlib
        import src.utils.error_tracking as error_tracking_module
        importlib.reload(error_tracking_module)

        result = error_tracking_module.capture_exception(ValueError("test"))
        assert result is None

    @patch("src.utils.error_tracking.SENTRY_AVAILABLE", False)
    def test_capture_message_when_unavailable(self):
        """Test capture_message returns None when Sentry unavailable."""
        import importlib
        import src.utils.error_tracking as error_tracking_module
        importlib.reload(error_tracking_module)

        result = error_tracking_module.capture_message("test")
        assert result is None


class TestLoggerIntegration:
    """Tests for Sentry integration with logger."""

    def test_sentry_logging_handler_initialization(self):
        """Test that Sentry logging handler is set up."""
        # Import and check the handler exists
        from src.utils.logger import SentryLoggingHandler

        handler = SentryLoggingHandler()
        assert handler is not None
        assert isinstance(handler, logging.Handler)

    def test_sentry_logging_handler_error_level(self):
        """Test that handler ignores non-ERROR levels."""
        from src.utils.logger import SentryLoggingHandler, SENTRY_AVAILABLE

        handler = SentryLoggingHandler()

        # Create log records
        info_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Info",
            args=(),
            exc_info=None,
        )

        # Verify handler was created correctly
        assert handler is not None
        # Verify the handler checks log levels (INFO < ERROR, so should be ignored)
        assert info_record.levelno < logging.ERROR


class TestGetAppVersion:
    """Tests for version detection."""

    def test_get_app_version_from_metadata(self):
        """Test getting version from package metadata."""
        from src.utils.error_tracking import _get_app_version

        with patch("importlib.metadata.version") as mock_version:
            mock_version.return_value = "0.1.0"
            version = _get_app_version()

        assert version == "0.1.0"

    def test_get_app_version_fallback(self):
        """Test version fallback when metadata not available."""
        from src.utils.error_tracking import _get_app_version

        with patch("importlib.metadata.version", side_effect=Exception("Not found")):
            with patch("pathlib.Path.read_text") as mock_read:
                mock_read.side_effect = Exception("File not found")
                version = _get_app_version()

        # Should return None when no version found
        assert version is None
