"""
Tests for logging and alerting system (Issue #103, QAQC-001).

This module tests:
- Safe expression evaluation (QAQC-001 security fix)
- Alert rule management
- Alert channels and notifications
- Log analysis and metrics extraction
- Security injection prevention
"""

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.utils.logging_alerting import (
    Alert,
    AlertChannel,
    AlertManager,
    AlertRule,
    AlertSeverity,
    LogAnalyzer,
    StructuredLogger,
    get_alert_manager,
    get_logger,
    reset_logging_instances,
)


class TestSafeExpressionEvaluation:
    """
    Security tests for the safe expression evaluator.

    These tests verify that the AST-based expression parser
    prevents code injection attacks while allowing legitimate
    alert conditions.
    """

    @pytest.fixture
    def alert_manager(self):
        """Create an alert manager for testing."""
        reset_logging_instances()
        manager = AlertManager()
        return manager

    # ==================== SECURITY TESTS ====================

    def test_eval_injection_os_system(self, alert_manager):
        """Test that os.system injection is blocked."""
        malicious = "__import__('os').system('rm -rf /')"
        with pytest.raises((ValueError, SyntaxError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_globals_builtins(self, alert_manager):
        """Test that globals()['__builtins__'] injection is blocked."""
        malicious = "globals()['__builtins__']"
        with pytest.raises((ValueError, AttributeError, TypeError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_class_mro(self, alert_manager):
        """Test that class MRO injection is blocked."""
        malicious = "().__class__.__mro__[1].__subclasses__()"
        with pytest.raises((ValueError, AttributeError, TypeError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_eval_call(self, alert_manager):
        """Test that eval() call injection is blocked."""
        malicious = "eval('malicious')"
        with pytest.raises((ValueError, SyntaxError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_exec_call(self, alert_manager):
        """Test that exec() call injection is blocked."""
        malicious = "exec('code')"
        with pytest.raises((ValueError, SyntaxError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_import(self, alert_manager):
        """Test that import injection is blocked."""
        malicious = "import os"
        with pytest.raises((ValueError, SyntaxError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_import_from(self, alert_manager):
        """Test that 'from x import y' injection is blocked."""
        malicious = "from os import system"
        with pytest.raises((ValueError, SyntaxError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_attribute_access(self, alert_manager):
        """Test that attribute access injection is blocked."""
        malicious = "cpu_usage.__class__.__name__"
        with pytest.raises(ValueError, match="Attribute access is not allowed"):
            alert_manager._evaluate_condition(malicious, metrics={"cpu_usage": 50})

    def test_eval_injection_subscript(self, alert_manager):
        """Test that subscript access injection is blocked."""
        malicious = "metrics['__builtins__']"
        with pytest.raises(ValueError, match="Subscript access is not allowed"):
            alert_manager._evaluate_condition(malicious, metrics={"metrics": {}})

    def test_eval_injection_lambda(self, alert_manager):
        """Test that lambda injection is blocked."""
        malicious = "(lambda: 1)()"
        with pytest.raises((ValueError, SyntaxError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_dict_literal(self, alert_manager):
        """Test that dict literal injection is blocked."""
        malicious = "{'key': 'value'}"
        with pytest.raises(ValueError, match="Dict literals are not allowed"):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_list_literal(self, alert_manager):
        """Test that list literal injection is blocked."""
        malicious = "[1, 2, 3]"
        with pytest.raises(ValueError, match="List literals are not allowed"):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_list_comprehension(self, alert_manager):
        """Test that list comprehension injection is blocked."""
        malicious = "[x for x in range(10)]"
        with pytest.raises((ValueError, SyntaxError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_assignment(self, alert_manager):
        """Test that assignment injection is blocked."""
        malicious = "x = 10"
        with pytest.raises((ValueError, SyntaxError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_builtins_access(self, alert_manager):
        """Test that __builtins__ access is blocked."""
        malicious = "__builtins__"
        with pytest.raises(ValueError, match="Access to '__builtins__' is not allowed"):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_globals_access(self, alert_manager):
        """Test that globals access is blocked."""
        malicious = "globals"
        with pytest.raises(ValueError, match="Access to 'globals' is not allowed"):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_locals_access(self, alert_manager):
        """Test that locals access is blocked."""
        malicious = "locals"
        with pytest.raises(ValueError, match="Access to 'locals' is not allowed"):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_open_call(self, alert_manager):
        """Test that open() call injection is blocked."""
        malicious = "open('/etc/passwd')"
        with pytest.raises((ValueError, SyntaxError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_input_call(self, alert_manager):
        """Test that input() call injection is blocked."""
        malicious = "input()"
        with pytest.raises((ValueError, SyntaxError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_yield(self, alert_manager):
        """Test that yield injection is blocked."""
        malicious = "yield 1"
        with pytest.raises((ValueError, SyntaxError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_assert(self, alert_manager):
        """Test that assert injection is blocked."""
        malicious = "assert False"
        with pytest.raises((ValueError, SyntaxError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_raise(self, alert_manager):
        """Test that raise injection is blocked."""
        malicious = "raise Exception()"
        with pytest.raises((ValueError, SyntaxError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    def test_eval_injection_delete(self, alert_manager):
        """Test that del injection is blocked."""
        malicious = "del x"
        with pytest.raises((ValueError, SyntaxError)):
            alert_manager._evaluate_condition(malicious, metrics={})

    # ==================== REGRESSION TESTS ====================

    def test_safe_comparison_greater_than(self, alert_manager):
        """Test that legitimate > comparison works."""
        result = alert_manager._evaluate_condition("cpu_usage > 80", {"cpu_usage": 90})
        assert result is True

        result = alert_manager._evaluate_condition("cpu_usage > 80", {"cpu_usage": 70})
        assert result is False

    def test_safe_comparison_less_than(self, alert_manager):
        """Test that legitimate < comparison works."""
        result = alert_manager._evaluate_condition("memory_mb < 1000", {"memory_mb": 500})
        assert result is True

        result = alert_manager._evaluate_condition("memory_mb < 1000", {"memory_mb": 1500})
        assert result is False

    def test_safe_comparison_equal(self, alert_manager):
        """Test that legitimate == comparison works."""
        result = alert_manager._evaluate_condition("status == 1", {"status": 1})
        assert result is True

        result = alert_manager._evaluate_condition("status == 1", {"status": 0})
        assert result is False

    def test_safe_comparison_not_equal(self, alert_manager):
        """Test that legitimate != comparison works."""
        result = alert_manager._evaluate_condition("status != 0", {"status": 1})
        assert result is True

        result = alert_manager._evaluate_condition("status != 0", {"status": 0})
        assert result is False

    def test_safe_comparison_greater_equal(self, alert_manager):
        """Test that legitimate >= comparison works."""
        result = alert_manager._evaluate_condition("cpu_usage >= 80", {"cpu_usage": 80})
        assert result is True

        result = alert_manager._evaluate_condition("cpu_usage >= 80", {"cpu_usage": 79})
        assert result is False

    def test_safe_comparison_less_equal(self, alert_manager):
        """Test that legitimate <= comparison works."""
        result = alert_manager._evaluate_condition("memory_mb <= 1000", {"memory_mb": 1000})
        assert result is True

        result = alert_manager._evaluate_condition("memory_mb <= 1000", {"memory_mb": 1001})
        assert result is False

    def test_safe_boolean_and(self, alert_manager):
        """Test that legitimate 'and' boolean operation works."""
        result = alert_manager._evaluate_condition(
            "cpu_usage > 80 and memory_mb > 500",
            {"cpu_usage": 90, "memory_mb": 600},
        )
        assert result is True

        result = alert_manager._evaluate_condition(
            "cpu_usage > 80 and memory_mb > 500",
            {"cpu_usage": 90, "memory_mb": 400},
        )
        assert result is False

    def test_safe_boolean_or(self, alert_manager):
        """Test that legitimate 'or' boolean operation works."""
        result = alert_manager._evaluate_condition(
            "cpu_usage > 80 or memory_mb > 500",
            {"cpu_usage": 70, "memory_mb": 600},
        )
        assert result is True

        result = alert_manager._evaluate_condition(
            "cpu_usage > 80 or memory_mb > 500",
            {"cpu_usage": 70, "memory_mb": 400},
        )
        assert result is False

    def test_safe_boolean_not(self, alert_manager):
        """Test that legitimate 'not' boolean operation works."""
        result = alert_manager._evaluate_condition("not error_flag", {"error_flag": False})
        assert result is True

        result = alert_manager._evaluate_condition("not error_flag", {"error_flag": True})
        assert result is False

    def test_safe_arithmetic_addition(self, alert_manager):
        """Test that legitimate addition works."""
        result = alert_manager._evaluate_condition("a + b > 10", {"a": 5, "b": 6})
        assert result is True

    def test_safe_arithmetic_subtraction(self, alert_manager):
        """Test that legitimate subtraction works."""
        result = alert_manager._evaluate_condition("a - b > 0", {"a": 10, "b": 5})
        assert result is True

    def test_safe_arithmetic_multiplication(self, alert_manager):
        """Test that legitimate multiplication works."""
        result = alert_manager._evaluate_condition("a * b > 20", {"a": 5, "b": 5})
        assert result is True

    def test_safe_arithmetic_division(self, alert_manager):
        """Test that legitimate division works."""
        result = alert_manager._evaluate_condition("a / b < 3", {"a": 10, "b": 5})
        assert result is True

    def test_safe_arithmetic_modulo(self, alert_manager):
        """Test that legitimate modulo works."""
        result = alert_manager._evaluate_condition("a % 2 == 0", {"a": 10})
        assert result is True

    def test_safe_arithmetic_power(self, alert_manager):
        """Test that legitimate power operation works."""
        result = alert_manager._evaluate_condition("a ** 2 > 20", {"a": 5})
        assert result is True

    def test_safe_unary_negation(self, alert_manager):
        """Test that legitimate unary negation works."""
        result = alert_manager._evaluate_condition("-a < 0", {"a": 5})
        assert result is True

    def test_safe_complex_expression(self, alert_manager):
        """Test that complex legitimate expressions work."""
        result = alert_manager._evaluate_condition(
            "(cpu_usage > 80 and memory_mb > 500) or error_rate > 0.1",
            {"cpu_usage": 90, "memory_mb": 600, "error_rate": 0.05},
        )
        assert result is True

        result = alert_manager._evaluate_condition(
            "(cpu_usage > 80 and memory_mb > 500) or error_rate > 0.1",
            {"cpu_usage": 70, "memory_mb": 400, "error_rate": 0.05},
        )
        assert result is False

    def test_safe_float_comparison(self, alert_manager):
        """Test that float comparisons work."""
        result = alert_manager._evaluate_condition("error_rate < 0.01", {"error_rate": 0.005})
        assert result is True

        result = alert_manager._evaluate_condition("error_rate < 0.01", {"error_rate": 0.05})
        assert result is False

    def test_safe_string_comparison(self, alert_manager):
        """Test that string comparisons work."""
        result = alert_manager._evaluate_condition('status == "ok"', {"status": "ok"})
        assert result is True

        result = alert_manager._evaluate_condition('status == "ok"', {"status": "error"})
        assert result is False

    def test_safe_boolean_literals(self, alert_manager):
        """Test that boolean literals work."""
        result = alert_manager._evaluate_condition("True", {})
        assert result is True

        result = alert_manager._evaluate_condition("False", {})
        assert result is False

    def test_safe_integer_literals(self, alert_manager):
        """Test that integer literals work in expressions."""
        result = alert_manager._evaluate_condition("value > 100", {"value": 150})
        assert result is True

    # ==================== EDGE CASE TESTS ====================

    def test_empty_condition_raises(self, alert_manager):
        """Test that empty condition raises ValueError."""
        with pytest.raises(ValueError, match="Condition cannot be empty"):
            alert_manager._evaluate_condition("", {})

    def test_whitespace_only_condition_raises(self, alert_manager):
        """Test that whitespace-only condition raises ValueError."""
        with pytest.raises(ValueError, match="Condition cannot be empty"):
            alert_manager._evaluate_condition("   ", {})

    def test_invalid_syntax_raises(self, alert_manager):
        """Test that invalid syntax raises SyntaxError."""
        with pytest.raises(SyntaxError):
            alert_manager._evaluate_condition("cpu_usage >", {"cpu_usage": 50})

    def test_non_string_condition_raises(self, alert_manager):
        """Test that non-string condition raises TypeError."""
        with pytest.raises(TypeError, match="Condition must be a string"):
            alert_manager._evaluate_condition(123, {})

    def test_unknown_variable_raises(self, alert_manager):
        """Test that unknown variable raises ValueError."""
        with pytest.raises(ValueError, match="Unknown variable"):
            alert_manager._evaluate_condition("unknown_var > 10", {"cpu_usage": 50})

    def test_nested_expression(self, alert_manager):
        """Test that nested expressions work."""
        result = alert_manager._evaluate_condition(
            "((a + b) * c) > 100",
            {"a": 5, "b": 5, "c": 15},
        )
        assert result is True


class TestAlertManager:
    """Tests for AlertManager functionality."""

    @pytest.fixture
    def alert_manager(self):
        """Create an alert manager for testing."""
        reset_logging_instances()
        return AlertManager()

    @pytest.mark.asyncio
    async def test_send_alert(self, alert_manager):
        """Test sending an alert."""
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
        assert alert.message == "Test message"

    @pytest.mark.asyncio
    async def test_add_and_trigger_rule(self, alert_manager):
        """Test adding and triggering an alert rule."""
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

    def test_get_alert_history_by_severity(self, alert_manager):
        """Test getting alert history filtered by severity."""
        alert_manager.alert_history = [
            Alert(
                name="Alert 1",
                severity=AlertSeverity.INFO,
                channel=AlertChannel.LOG,
                message="Info message",
                metadata={},
            ),
            Alert(
                name="Alert 2",
                severity=AlertSeverity.ERROR,
                channel=AlertChannel.LOG,
                message="Error message",
                metadata={},
            ),
        ]

        history = alert_manager.get_alert_history(severity=AlertSeverity.ERROR)
        assert len(history) == 1
        assert history[0].severity == AlertSeverity.ERROR

    def test_get_metrics(self, alert_manager):
        """Test getting alert metrics."""
        alert_manager.alert_history = [
            Alert(
                name="Alert 1",
                severity=AlertSeverity.INFO,
                channel=AlertChannel.LOG,
                message="Message 1",
                metadata={},
            ),
            Alert(
                name="Alert 2",
                severity=AlertSeverity.ERROR,
                channel=AlertChannel.LOG,
                message="Message 2",
                metadata={},
            ),
        ]

        alert_manager.add_rule(AlertRule(
            name="test_rule",
            condition="x > 1",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.LOG],
        ))

        metrics = alert_manager.get_metrics()
        assert metrics["total_alerts"] == 2
        assert metrics["active_rules"] == 1

    def test_remove_rule(self, alert_manager):
        """Test removing an alert rule."""
        rule = AlertRule(
            name="test_rule",
            condition="x > 1",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.LOG],
        )

        alert_manager.add_rule(rule)
        assert "test_rule" in alert_manager.alert_rules

        alert_manager.remove_rule("test_rule")
        assert "test_rule" not in alert_manager.alert_rules


class TestStructuredLogger:
    """Tests for StructuredLogger functionality."""

    @pytest.fixture
    def temp_log_file(self):
        """Create a temporary log file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            yield f.name
        Path(f.name).unlink(missing_ok=True)

    def test_create_logger(self):
        """Test creating a logger."""
        reset_logging_instances()
        logger = get_logger("test_logger")
        assert logger is not None
        assert logger.name == "test_logger"

    def test_logger_with_context(self):
        """Test creating a logger with context."""
        reset_logging_instances()
        logger = get_logger("test_logger")
        contextual_logger = logger.with_context(task_id="123", user_id="456")

        assert contextual_logger.context["task_id"] == "123"
        assert contextual_logger.context["user_id"] == "456"
        assert contextual_logger.name == "test_logger"

    def test_log_methods(self, caplog):
        """Test various log methods."""
        reset_logging_instances()
        logger = get_logger("test_logger", level=logging.DEBUG)

        with caplog.at_level(logging.DEBUG):
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

        assert "Debug message" in caplog.text
        assert "Info message" in caplog.text
        assert "Warning message" in caplog.text
        assert "Error message" in caplog.text


class TestLogAnalyzer:
    """Tests for LogAnalyzer functionality."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_parse_logs(self, temp_log_dir):
        """Test parsing log files."""
        log_path = Path(temp_log_dir) / "test.log"
        log_data = [
            {"timestamp": "2024-01-01T00:00:00Z", "level": "INFO", "message": "Test 1"},
            {"timestamp": "2024-01-01T00:00:01Z", "level": "ERROR", "message": "Test 2"},
        ]

        with open(log_path, 'w') as f:
            for entry in log_data:
                f.write(json.dumps(entry) + "\n")

        analyzer = LogAnalyzer(log_dir=temp_log_dir)
        parsed = analyzer.parse_logs("test.log")

        assert len(parsed) == 2
        assert parsed[0]["level"] == "INFO"
        assert parsed[1]["level"] == "ERROR"

    def test_parse_nonexistent_file(self, temp_log_dir):
        """Test parsing a nonexistent log file."""
        analyzer = LogAnalyzer(log_dir=temp_log_dir)
        parsed = analyzer.parse_logs("nonexistent.log")
        assert parsed == []

    def test_extract_metrics(self, temp_log_dir):
        """Test extracting metrics from logs."""
        logs = [
            {"level": "INFO", "response_time_ms": 100},
            {"level": "INFO", "response_time_ms": 200},
            {"level": "ERROR", "response_time_ms": 500},
        ]

        analyzer = LogAnalyzer(log_dir=temp_log_dir)
        metrics = analyzer.extract_metrics(logs)

        assert metrics["total_logs"] == 3
        assert metrics["error_rate"] == 1/3
        assert metrics["avg_response_time"] == (100 + 200 + 500) / 3

    def test_detect_anomalies(self, temp_log_dir):
        """Test detecting anomalies in metrics."""
        baseline = {"error_rate": 0.01, "avg_response_time": 100}
        current = {"error_rate": 0.05, "avg_response_time": 500}

        analyzer = LogAnalyzer(log_dir=temp_log_dir)
        anomalies = analyzer.detect_anomalies(current, baseline, threshold=2.0)

        assert len(anomalies) == 2
        assert any("Error rate" in a for a in anomalies)
        assert any("Response time" in a for a in anomalies)


# Import json here to avoid issues with test discovery
import json
