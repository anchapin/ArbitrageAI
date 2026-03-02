"""
Tests for Graceful Shutdown (Issue #102) and Logging/Alerting (Issue #103)
"""

import pytest
import asyncio
import signal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import json

from src.utils.graceful_shutdown import (
    GracefulShutdownManager,
    ShutdownReason,
    ShutdownState,
    get_shutdown_manager,
    reset_shutdown_manager,
)

from src.utils.logging_alerting import (
    StructuredLogger,
    AlertManager,
    AlertRule,
    AlertSeverity,
    AlertChannel,
    Alert,
    LogAnalyzer,
    get_logger,
    get_alert_manager,
    reset_logging_instances,
)


# =============================================================================
# Graceful Shutdown Tests
# =============================================================================

class TestShutdownManager:
    """Test graceful shutdown manager."""

    @pytest.fixture
    def shutdown_manager(self, tmp_path):
        """Create shutdown manager with temp directory."""
        manager = GracefulShutdownManager(state_dir=str(tmp_path))
        return manager

    def test_initialization(self, shutdown_manager):
        """Test shutdown manager initializes correctly."""
        assert shutdown_manager.state == ShutdownState.RUNNING
        assert shutdown_manager.shutdown_reason is None
        assert shutdown_manager.shutdown_handlers == {}

    @pytest.mark.asyncio
    async def test_register_handler(self, shutdown_manager):
        """Test registering shutdown handler."""
        async def cleanup():
            pass
        
        shutdown_manager.register_handler("test", cleanup)
        assert "test" in shutdown_manager.shutdown_handlers

    @pytest.mark.asyncio
    async def test_unregister_handler(self, shutdown_manager):
        """Test unregistering shutdown handler."""
        async def cleanup():
            pass
        
        shutdown_manager.register_handler("test", cleanup)
        shutdown_manager.unregister_handler("test")
        assert "test" not in shutdown_manager.shutdown_handlers

    @pytest.mark.asyncio
    async def test_register_task(self, shutdown_manager):
        """Test registering active task."""
        shutdown_manager.register_task("task_123", {"title": "Test Task"})
        assert "task_123" in shutdown_manager.active_tasks

    @pytest.mark.asyncio
    async def test_unregister_task(self, shutdown_manager):
        """Test unregistering task."""
        shutdown_manager.register_task("task_123", {"title": "Test Task"})
        shutdown_manager.unregister_task("task_123")
        assert "task_123" not in shutdown_manager.active_tasks

    @pytest.mark.asyncio
    async def test_shutdown_state_transition(self, shutdown_manager):
        """Test shutdown state transitions."""
        assert shutdown_manager.state == ShutdownState.RUNNING
        
        await shutdown_manager.shutdown(ShutdownReason.MANUAL)
        
        assert shutdown_manager.state == ShutdownState.SHUTDOWN_COMPLETE
        assert shutdown_manager.shutdown_reason == ShutdownReason.MANUAL

    @pytest.mark.asyncio
    async def test_shutdown_saves_state(self, shutdown_manager, tmp_path):
        """Test shutdown saves state to disk."""
        shutdown_manager.register_task("task_123", {"title": "Test"})
        shutdown_manager.pending_jobs.append({"job_id": "job_456"})
        
        await shutdown_manager.shutdown(ShutdownReason.MANUAL)
        
        state_file = tmp_path / "shutdown_state.json"
        assert state_file.exists()
        
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        
        assert len(state_data["active_tasks"]) == 1
        assert len(state_data["pending_jobs"]) == 1

    @pytest.mark.asyncio
    async def test_is_shutting_down(self, shutdown_manager):
        """Test shutdown status check."""
        assert not shutdown_manager.is_shutting_down()
        
        await shutdown_manager.shutdown(ShutdownReason.MANUAL)
        
        assert shutdown_manager.is_shutting_down()

    @pytest.mark.asyncio
    async def test_get_status(self, shutdown_manager):
        """Test getting shutdown manager status."""
        shutdown_manager.register_task("task_123", {"title": "Test"})
        
        status = shutdown_manager.get_status()
        
        assert status["state"] == "running"
        assert status["active_tasks"] == 1
        assert "uptime_seconds" in status

    @pytest.mark.asyncio
    async def test_handler_timeout(self, shutdown_manager):
        """Test handler timeout handling."""
        async def slow_handler():
            await asyncio.sleep(10)
        
        shutdown_manager.register_handler("slow", slow_handler)
        shutdown_manager.shutdown_timeout = 1.0
        
        await shutdown_manager.shutdown(ShutdownReason.MANUAL)
        # Should complete without hanging


class TestGracefulShutdownGlobal:
    """Test global shutdown manager."""

    def test_get_shutdown_manager(self):
        """Test getting global shutdown manager."""
        manager = get_shutdown_manager()
        assert manager is not None
        assert isinstance(manager, GracefulShutdownManager)

    def test_reset_shutdown_manager(self):
        """Test resetting global shutdown manager."""
        get_shutdown_manager()
        reset_shutdown_manager()
        manager = get_shutdown_manager()
        assert manager is not None


# =============================================================================
# Logging and Alerting Tests
# =============================================================================

class TestStructuredLogger:
    """Test structured logger."""

    @pytest.fixture
    def logger(self, tmp_path):
        """Create structured logger."""
        log_file = tmp_path / "test.log"
        return StructuredLogger(
            name="test_logger",
            log_file=str(log_file),
            enable_json=True,
        )

    def test_logger_creation(self, logger):
        """Test logger creation."""
        assert logger is not None
        assert logger.name == "test_logger"

    def test_logger_info(self, logger, caplog):
        """Test logging info message."""
        logger.info("Test message")
        assert "Test message" in caplog.text

    def test_logger_with_context(self, logger):
        """Test logger with context."""
        contextual_logger = logger.with_context(task_id="123", user="test")
        assert contextual_logger.context["task_id"] == "123"
        assert contextual_logger.context["user"] == "test"

    def test_logger_json_format(self, logger, tmp_path):
        """Test JSON log format."""
        logger.info("JSON test", extra={"key": "value"})
        
        log_file = tmp_path / "test.log"
        with open(log_file, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            
            assert log_data["level"] == "INFO"
            assert log_data["message"] == "JSON test"
            assert log_data["key"] == "value"


class TestAlertManager:
    """Test alert manager."""

    @pytest.fixture
    def alert_manager(self, tmp_path):
        """Create alert manager."""
        return AlertManager(log_dir=str(tmp_path))

    def test_alert_manager_creation(self, alert_manager):
        """Test alert manager creation."""
        assert alert_manager is not None
        assert alert_manager.alert_rules == {}

    def test_add_rule(self, alert_manager):
        """Test adding alert rule."""
        rule = AlertRule(
            name="test_rule",
            condition="error_count > 10",
            severity=AlertSeverity.ERROR,
            channels=[AlertChannel.LOG],
        )
        
        alert_manager.add_rule(rule)
        assert "test_rule" in alert_manager.alert_rules

    def test_remove_rule(self, alert_manager):
        """Test removing alert rule."""
        rule = AlertRule(
            name="test_rule",
            condition="error_count > 10",
            severity=AlertSeverity.ERROR,
            channels=[AlertChannel.LOG],
        )
        
        alert_manager.add_rule(rule)
        alert_manager.remove_rule("test_rule")
        assert "test_rule" not in alert_manager.alert_rules

    @pytest.mark.asyncio
    async def test_send_alert(self, alert_manager):
        """Test sending alert."""
        await alert_manager.send_alert(
            name="Test Alert",
            severity=AlertSeverity.WARNING,
            message="Test message",
            metadata={"key": "value"},
        )
        
        assert len(alert_manager.alert_history) == 1
        alert = alert_manager.alert_history[0]
        assert alert.name == "Test Alert"
        assert alert.severity == AlertSeverity.WARNING

    @pytest.mark.asyncio
    async def test_check_rules(self, alert_manager):
        """Test checking alert rules."""
        rule = AlertRule(
            name="high_error_rate",
            condition="error_rate > 0.1",
            severity=AlertSeverity.ERROR,
            channels=[AlertChannel.LOG],
            cooldown_seconds=0,  # No cooldown for testing
        )

        alert_manager.add_rule(rule)

        # Trigger rule
        metrics = {"error_rate": 0.15}
        alert_manager.check_rules(metrics)
        
        # Give async task time to complete
        await asyncio.sleep(0.1)

        # Rule should have been triggered
        assert rule.last_triggered is not None

    def test_get_alert_history(self, alert_manager):
        """Test getting alert history."""
        alert_manager.alert_history = [
            Alert(
                name=f"Alert {i}",
                severity=AlertSeverity.INFO,
                channel=AlertChannel.LOG,
                message=f"Message {i}",
                metadata={},
            )
            for i in range(5)
        ]
        
        history = alert_manager.get_alert_history(limit=3)
        assert len(history) == 3

    def test_get_metrics(self, alert_manager):
        """Test getting alert metrics."""
        alert_manager.alert_history = [
            Alert(
                name="Alert 1",
                severity=AlertSeverity.ERROR,
                channel=AlertChannel.LOG,
                message="Error",
                metadata={},
            ),
            Alert(
                name="Alert 2",
                severity=AlertSeverity.WARNING,
                channel=AlertChannel.LOG,
                message="Warning",
                metadata={},
            ),
        ]
        
        metrics = alert_manager.get_metrics()
        assert metrics["total_alerts"] == 2
        assert "alerts_by_severity" in metrics


class TestLogAnalyzer:
    """Test log analyzer."""

    @pytest.fixture
    def analyzer(self, tmp_path):
        """Create log analyzer."""
        return LogAnalyzer(log_dir=str(tmp_path))

    def test_parse_logs(self, analyzer, tmp_path):
        """Test parsing log file."""
        # Create test log file
        log_file = tmp_path / "test.log"
        logs = [
            {"level": "INFO", "message": "Test 1"},
            {"level": "ERROR", "message": "Test 2"},
        ]
        
        with open(log_file, 'w') as f:
            for log in logs:
                f.write(json.dumps(log) + "\n")
        
        parsed = analyzer.parse_logs("test.log")
        assert len(parsed) == 2

    def test_extract_metrics(self, analyzer):
        """Test extracting metrics from logs."""
        logs = [
            {"level": "INFO", "message": "Test", "response_time_ms": 100},
            {"level": "INFO", "message": "Test", "response_time_ms": 200},
            {"level": "ERROR", "message": "Error"},
        ]
        
        metrics = analyzer.extract_metrics(logs)
        
        assert metrics["total_logs"] == 3
        assert metrics["by_level"]["INFO"] == 2
        assert metrics["by_level"]["ERROR"] == 1
        assert metrics["error_rate"] == 1/3
        assert metrics["avg_response_time"] == 150

    def test_detect_anomalies(self, analyzer):
        """Test anomaly detection."""
        baseline = {
            "error_rate": 0.01,
            "avg_response_time": 100,
        }
        
        current = {
            "error_rate": 0.1,  # 10x higher
            "avg_response_time": 500,  # 5x higher
        }
        
        anomalies = analyzer.detect_anomalies(current, baseline, threshold=2.0)
        assert len(anomalies) > 0


class TestLoggingGlobal:
    """Test global logging instances."""

    def test_get_logger(self):
        """Test getting logger."""
        logger = get_logger("test")
        assert logger is not None
        assert isinstance(logger, StructuredLogger)

    def test_get_alert_manager(self):
        """Test getting alert manager."""
        manager = get_alert_manager()
        assert manager is not None
        assert isinstance(manager, AlertManager)

    def test_reset_logging_instances(self):
        """Test resetting logging instances."""
        get_logger("test")
        get_alert_manager()
        reset_logging_instances()
