"""
Logging and Alerting System (Issue #103).

Provides comprehensive logging and alerting capabilities:
- Structured logging with multiple levels
- Log aggregation and rotation
- Alert rules and notifications
- Integration with monitoring systems
- Log-based metrics and analytics

Features:
- JSON structured logging
- Log rotation and retention
- Alert rule engine
- Multiple alert channels (email, webhook, Slack)
- Log filtering and sampling
- Performance metrics extraction

Usage:
    from src.utils.logging_alerting import get_logger, AlertManager

    logger = get_logger(__name__)
    logger.info("Task started", extra={"task_id": "123"})

    alert_manager = AlertManager()
    await alert_manager.send_alert("High Error Rate", "error_rate", {"rate": 0.15})
"""

import ast
import asyncio
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
from typing import Any

import aiohttp

from .telemetry import get_tracer


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    """Alert notification channels."""
    LOG = "log"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"


@dataclass
class Alert:
    """Alert data structure."""
    name: str
    severity: AlertSeverity
    channel: AlertChannel
    message: str
    metadata: dict[str, Any]
    timestamp: str = ""
    triggered_count: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class AlertRule:
    """Alert rule definition."""
    name: str
    condition: str  # e.g., "error_count > 10"
    severity: AlertSeverity
    channels: list[AlertChannel]
    cooldown_seconds: int = 300
    enabled: bool = True
    last_triggered: datetime | None = None


class StructuredLogger:
    """
    Structured logger with JSON formatting and context support.

    Features:
    - JSON structured logging
    - Context injection
    - Log level filtering
    - Performance metrics
    """

    def __init__(
        self,
        name: str,
        level: int = logging.INFO,
        log_file: str | None = None,
        enable_json: bool = True,
        context: dict[str, Any] | None = None,
    ):
        """Initialize the structured logger.

        Args:
            name: Logger name.
            level: Logging level.
            log_file: Optional file path for log output.
            enable_json: Whether to use JSON formatting.
            context: Additional context to include in logs.
        """
        self.name = name
        self.context = context or {}
        self.enable_json = enable_json

        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Clear existing handlers
        self.logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        if enable_json:
            console_handler.setFormatter(self._json_formatter())
        else:
            console_handler.setFormatter(logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            ))
        self.logger.addHandler(console_handler)

        # File handler (if specified)
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
            )
            file_handler.setLevel(level)
            if enable_json:
                file_handler.setFormatter(self._json_formatter())
            self.logger.addHandler(file_handler)

    def _json_formatter(self) -> logging.Formatter:
        """Create JSON log formatter."""
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }

                # Add extra fields
                if hasattr(record, "context"):
                    log_data.update(record.context)

                # Add exception info if present
                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)

                return json.dumps(log_data)

        return JSONFormatter()

    def _log(
        self,
        level: int,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Internal log method with context."""
        context = {**self.context, **(extra or {})}
        extra = {"context": context}

        # Get the correct stack frame
        frame = sys._getframe(2)
        extra["context"]["file"] = frame.f_code.co_filename
        extra["context"]["line"] = frame.f_lineno
        extra["context"]["function"] = frame.f_code.co_name

        self.logger.log(level, message, extra=extra)

    def debug(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, extra)

    def info(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """Log info message."""
        self._log(logging.INFO, message, extra)

    def warning(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, extra)

    def error(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """Log error message."""
        self._log(logging.ERROR, message, extra)

    def critical(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, message, extra)

    def exception(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """Log exception with traceback."""
        self.logger.exception(message, extra={"context": {**self.context, **(extra or {})}})

    def with_context(self, **kwargs) -> "StructuredLogger":
        """Create a new logger with additional context."""
        new_context = {**self.context, **kwargs}
        return StructuredLogger(
            self.name,
            level=self.logger.level,
            context=new_context,
            enable_json=self.enable_json,
        )


class AlertManager:
    """
    Alert management system with rule-based triggering.

    Features:
    - Rule-based alert triggering
    - Multiple notification channels
    - Cooldown and deduplication
    - Alert history and analytics
    """

    def __init__(
        self,
        log_dir: str = "logs/alerts",
        webhook_url: str | None = None,
        slack_webhook: str | None = None,
    ):
        """Initialize the alert manager.

        Args:
            log_dir: Directory to store alert logs.
            webhook_url: Optional webhook URL for alerts.
            slack_webhook: Optional Slack webhook URL.
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.webhook_url = webhook_url
        self.slack_webhook = slack_webhook

        self.alert_rules: dict[str, AlertRule] = {}
        self.alert_history: list[Alert] = []
        self.metrics: dict[str, Any] = defaultdict(int)
        self._tracer = get_tracer("alerting")

    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule."""
        self.alert_rules[rule.name] = rule
        logging.info(f"Added alert rule: {rule.name}")

    def remove_rule(self, name: str) -> None:
        """Remove an alert rule."""
        if name in self.alert_rules:
            del self.alert_rules[name]
            logging.info(f"Removed alert rule: {name}")

    async def send_alert(
        self,
        name: str,
        severity: AlertSeverity,
        message: str,
        metadata: dict[str, Any] | None = None,
        channel: AlertChannel = AlertChannel.LOG,
    ) -> None:
        """
        Send an alert.

        Args:
            name: Alert name
            severity: Alert severity
            message: Alert message
            metadata: Additional metadata
            channel: Notification channel
        """
        alert = Alert(
            name=name,
            severity=severity,
            channel=channel,
            message=message,
            metadata=metadata or {},
        )

        # Add to history
        self.alert_history.append(alert)

        # Log alert
        log_method = logging.warning if severity == AlertSeverity.WARNING else logging.error
        log_method(f"ALERT [{severity.value.upper()}]: {name} - {message}")

        # Send to channels
        await self._send_to_channels(alert)

    async def _send_to_channels(self, alert: Alert) -> None:
        """Send alert to configured channels."""
        tasks = []

        if alert.channel == AlertChannel.WEBHOOK and self.webhook_url:
            tasks.append(self._send_webhook(alert))

        if alert.channel == AlertChannel.SLACK and self.slack_webhook:
            tasks.append(self._send_slack(alert))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_webhook(self, alert: Alert) -> None:
        """Send alert to webhook."""
        try:
            async with aiohttp.ClientSession() as session, session.post(
                self.webhook_url,
                json=asdict(alert),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    logging.info(f"Alert sent to webhook: {alert.name}")
                else:
                    logging.error(f"Webhook alert failed: {response.status}")
        except Exception as e:
            logging.error(f"Webhook alert error: {e}")

    async def _send_slack(self, alert: Alert) -> None:
        """Send alert to Slack."""
        try:
            color = {
                AlertSeverity.INFO: "good",
                AlertSeverity.WARNING: "warning",
                AlertSeverity.ERROR: "danger",
                AlertSeverity.CRITICAL: "danger",
            }.get(alert.severity, "warning")

            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"{alert.severity.value.upper()}: {alert.name}",
                        "text": alert.message,
                        "fields": [
                            {"title": k, "value": str(v), "short": True}
                            for k, v in alert.metadata.items()
                        ],
                        "ts": int(datetime.now(timezone.utc).timestamp()),
                    },
                ],
            }

            async with aiohttp.ClientSession() as session, session.post(
                self.slack_webhook,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    logging.info(f"Alert sent to Slack: {alert.name}")
                else:
                    logging.error(f"Slack alert failed: {response.status}")
        except Exception as e:
            logging.error(f"Slack alert error: {e}")

    def check_rules(self, metrics: dict[str, Any]) -> None:
        """
        Check alert rules against current metrics.

        Args:
            metrics: Current system metrics
        """
        for rule in self.alert_rules.values():
            if not rule.enabled:
                continue

            # Check cooldown
            if rule.last_triggered:
                elapsed = (datetime.now(timezone.utc) - rule.last_triggered).total_seconds()
                if elapsed < rule.cooldown_seconds:
                    continue

            # Evaluate condition
            if self._evaluate_condition(rule.condition, metrics):
                # Trigger alert
                asyncio.create_task(self._trigger_rule(rule, metrics))
                rule.last_triggered = datetime.now(timezone.utc)

    def _evaluate_condition(self, condition: str, metrics: dict[str, Any]) -> bool:
        """
        Evaluate an alert condition using a safe AST-based expression parser.

        Example condition: "error_count > 10"

        This implementation uses a custom AST visitor that only allows safe operations:
        - Numeric literals (int, float)
        - String literals
        - Boolean literals (True, False)
        - Variable references (from metrics dict only)
        - Comparison operators: ==, !=, <, <=, >, >=
        - Boolean operators: and, or, not
        - Arithmetic operators: +, -, *, /, %, **

        Security features:
        - No function calls allowed
        - No attribute access allowed
        - No subscript access allowed
        - No imports allowed
        - No builtins access
        - Whitelist-based operator approval

        Args:
            condition: Expression string to evaluate
            metrics: Dictionary of metric variables available to the expression

        Returns:
            Boolean result of the condition evaluation

        Raises:
            ValueError: If the expression contains unsafe operations
            SyntaxError: If the expression has invalid syntax
        """
        import operator

        # Define allowed operators for safe expression evaluation
        # Only whitelisted operators are permitted
        allowed_operators = {
            # Arithmetic operators
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
            # Comparison operators
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
            # Boolean operators
            ast.And: operator.and_,
            ast.Or: operator.or_,
            ast.Not: operator.not_,
        }

        # Explicitly blocked AST node types for security
        # These would allow code injection or access to sensitive data
        # Note: ast.Exec doesn't exist in Python 3.x (exec is a function, not a statement)
        blocked_nodes = {
            ast.Call: "Function calls are not allowed",
            ast.Attribute: "Attribute access is not allowed",
            ast.Subscript: "Subscript access is not allowed",
            ast.Import: "Imports are not allowed",
            ast.ImportFrom: "Imports are not allowed",
            ast.Lambda: "Lambda functions are not allowed",
            ast.Dict: "Dict literals are not allowed in conditions",
            ast.Set: "Set literals are not allowed in conditions",
            ast.Tuple: "Tuple literals are not allowed in conditions",
            ast.List: "List literals are not allowed in conditions",
            ast.ListComp: "List comprehensions are not allowed",
            ast.SetComp: "Set comprehensions are not allowed",
            ast.DictComp: "Dict comprehensions are not allowed",
            ast.GeneratorExp: "Generator expressions are not allowed",
            ast.Yield: "Yield is not allowed",
            ast.YieldFrom: "Yield from is not allowed",
            ast.Await: "Await is not allowed",
            ast.Assign: "Assignment is not allowed",
            ast.AnnAssign: "Annotated assignment is not allowed",
            ast.AugAssign: "Augmented assignment is not allowed",
            ast.Delete: "Delete is not allowed",
            ast.Raise: "Raise is not allowed",
            ast.Assert: "Assert is not allowed",
        }

        def _check_blocked_nodes(node) -> None:
            """Recursively check for blocked node types."""
            if type(node) in blocked_nodes:
                raise ValueError(blocked_nodes[type(node)])
            # Recursively check child nodes
            for child in ast.iter_child_nodes(node):
                _check_blocked_nodes(child)

        def eval_node(node):
            """
            Safely evaluate an AST node.

            This function only processes whitelisted node types and operators.
            Any attempt to use blocked operations will raise ValueError.
            """
            # Check for blocked node types first
            _check_blocked_nodes(node)

            # Handle constants (Python 3.8+: combines Num, Str, NameConstant)
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float, str, bool)):
                    return node.value
                raise ValueError(f"Unsupported constant type: {type(node.value)}")

            # Handle legacy Python 3.7 and earlier (for backwards compatibility)
            # Suppress deprecation warnings for legacy AST nodes
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                if isinstance(node, ast.Num):  # Deprecated in Python 3.8
                    return node.n
                if isinstance(node, ast.Str):  # Deprecated in Python 3.8
                    return node.s
                if isinstance(node, ast.NameConstant):  # Deprecated in Python 3.8
                    return node.value

            # Handle variable references
            if isinstance(node, ast.Name):
                if node.id in metrics:
                    return metrics[node.id]
                # Check for common injection attempts
                if node.id in ("__builtins__", "globals", "locals", "eval", "exec",
                               "__import__", "open", "input"):
                    raise ValueError(f"Access to '{node.id}' is not allowed")
                raise ValueError(f"Unknown variable: {node.id}")

            # Handle comparison operations (e.g., x > 5, x == y)
            if isinstance(node, ast.Compare):
                left = eval_node(node.left)
                for op, right in zip(node.ops, node.comparators, strict=False):
                    if type(op) not in allowed_operators:
                        raise ValueError(f"Unsupported comparison operator: {type(op).__name__}")
                    left = allowed_operators[type(op)](left, eval_node(right))
                return left

            # Handle boolean operations (and, or)
            if isinstance(node, ast.BoolOp):
                result = eval_node(node.values[0])
                for value in node.values[1:]:
                    result = allowed_operators[type(node.op)](result, eval_node(value))
                return result

            # Handle unary operations (not, -, +)
            if isinstance(node, ast.UnaryOp):
                if type(node.op) not in allowed_operators:
                    raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
                return allowed_operators[type(node.op)](eval_node(node.operand))

            # Handle binary operations (+, -, *, /, etc.)
            if isinstance(node, ast.BinOp):
                if type(node.op) not in allowed_operators:
                    raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
                return allowed_operators[type(node.op)](
                    eval_node(node.left),
                    eval_node(node.right),
                )

            # Any other node type is rejected
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")

        # Validate input
        if not isinstance(condition, str):
            raise TypeError("Condition must be a string")
        if not condition.strip():
            raise ValueError("Condition cannot be empty")

        # Parse the condition into an AST
        # mode="eval" ensures we only parse expressions, not statements
        try:
            tree = ast.parse(condition.strip(), mode="eval")
        except SyntaxError as e:
            raise SyntaxError(f"Invalid syntax in condition: {e}") from e

        # Evaluate the expression safely
        # tree.body contains the expression node directly when mode="eval"
        return bool(eval_node(tree.body))

    async def _trigger_rule(
        self,
        rule: AlertRule,
        metrics: dict[str, Any],
    ) -> None:
        """Trigger an alert from a rule."""
        for channel in rule.channels:
            await self.send_alert(
                name=rule.name,
                severity=rule.severity,
                message=f"Alert rule triggered: {rule.condition}",
                metadata={"metrics": metrics},
                channel=channel,
            )

    def get_alert_history(
        self,
        limit: int = 100,
        severity: AlertSeverity | None = None,
    ) -> list[Alert]:
        """Get alert history."""
        history = self.alert_history

        if severity:
            history = [a for a in history if a.severity == severity]

        return history[-limit:]

    def get_metrics(self) -> dict[str, Any]:
        """Get alert metrics."""
        return {
            "total_alerts": len(self.alert_history),
            "alerts_by_severity": {
                severity.value: len([a for a in self.alert_history if a.severity == severity])
                for severity in AlertSeverity
            },
            "active_rules": len([r for r in self.alert_rules.values() if r.enabled]),
        }


class LogAnalyzer:
    """
    Log analysis and metrics extraction.

    Features:
    - Log parsing and filtering
    - Metrics extraction
    - Trend analysis
    - Anomaly detection
    """

    def __init__(self, log_dir: str = "logs"):
        """Initialize the log analyzer.

        Args:
            log_dir: Directory containing log files.
        """
        self.log_dir = Path(log_dir)

    def parse_logs(self, log_file: str) -> list[dict[str, Any]]:
        """Parse log file and extract structured data."""
        log_path = self.log_dir / log_file

        if not log_path.exists():
            return []

        logs = []
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                try:
                    log_data = json.loads(line.strip())
                    logs.append(log_data)
                except json.JSONDecodeError:
                    continue

        return logs

    def extract_metrics(self, logs: list[dict[str, Any]]) -> dict[str, Any]:
        """Extract metrics from logs."""
        metrics = {
            "total_logs": len(logs),
            "by_level": defaultdict(int),
            "by_logger": defaultdict(int),
            "error_rate": 0.0,
            "avg_response_time": 0.0,
        }

        response_times = []

        for log in logs:
            metrics["by_level"][log.get("level", "UNKNOWN")] += 1
            metrics["by_logger"][log.get("logger", "unknown")] += 1

            if "response_time_ms" in log:
                response_times.append(log["response_time_ms"])

        # Calculate error rate
        error_count = metrics["by_level"].get("ERROR", 0) + metrics["by_level"].get("CRITICAL", 0)
        if metrics["total_logs"] > 0:
            metrics["error_rate"] = error_count / metrics["total_logs"]

        # Calculate average response time
        if response_times:
            metrics["avg_response_time"] = sum(response_times) / len(response_times)

        return metrics

    def detect_anomalies(
        self,
        metrics: dict[str, Any],
        baseline: dict[str, Any],
        threshold: float = 2.0,
    ) -> list[str]:
        """
        Detect anomalies in metrics compared to baseline.

        Args:
            metrics: Current metrics
            baseline: Baseline metrics
            threshold: Standard deviations for anomaly detection

        Returns:
            List of anomaly descriptions
        """
        anomalies = []

        # Check error rate
        if "error_rate" in metrics and "error_rate" in baseline:
            if baseline["error_rate"] > 0:
                ratio = metrics["error_rate"] / baseline["error_rate"]
                if ratio > threshold:
                    anomalies.append(
                        f"Error rate {ratio:.2f}x higher than baseline",
                    )

        # Check response time
        if "avg_response_time" in metrics and "avg_response_time" in baseline:
            if baseline["avg_response_time"] > 0:
                ratio = metrics["avg_response_time"] / baseline["avg_response_time"]
                if ratio > threshold:
                    anomalies.append(
                        f"Response time {ratio:.2f}x higher than baseline",
                    )

        return anomalies


# Global instances
_loggers: dict[str, StructuredLogger] = {}
_alert_manager: AlertManager | None = None


def get_logger(
    name: str,
    level: int = logging.INFO,
    log_file: str | None = None,
    enable_json: bool = True,
) -> StructuredLogger:
    """Get or create a structured logger."""
    if name not in _loggers:
        if log_file is None:
            log_file = os.getenv("LOG_FILE", f"logs/{name.replace('.', '/')}.log")

        _loggers[name] = StructuredLogger(
            name=name,
            level=level,
            log_file=log_file,
            enable_json=enable_json,
        )

    return _loggers[name]


def get_alert_manager() -> AlertManager:
    """Get or create the alert manager."""
    global _alert_manager  # noqa: PLW0603
    if _alert_manager is None:
        _alert_manager = AlertManager(
            webhook_url=os.getenv("ALERT_WEBHOOK_URL"),
            slack_webhook=os.getenv("SLACK_WEBHOOK_URL"),
        )
    return _alert_manager


def reset_logging_instances() -> None:
    """Reset global logging instances (for testing)."""
    global _loggers, _alert_manager  # noqa: PLW0603
    _loggers.clear()
    _alert_manager = None
