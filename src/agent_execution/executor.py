"""
E2B Code Interpreter Executor - Core Module.

This module provides the core sandbox execution functionality.
For task routing and document generation, use the specialized modules:
- task_router: TaskRouter class
- data_viz: execute_data_visualization function
- document_gen: DocumentGenerator, ReportGenerator classes
- types: TaskType, OutputFormat, configuration constants
"""

import asyncio
import os
from typing import Any

# E2B Code Interpreter SDK (fallback)
try:
    from e2b_code_interpreter import Sandbox
    E2B_AVAILABLE = True
except ImportError:
    E2B_AVAILABLE = False
    Sandbox = None

# Docker Sandbox (primary - for cost savings)
try:
    from src.agent_execution.docker_sandbox import LocalDockerSandbox, SandboxResult
    DOCKER_SANDBOX_AVAILABLE = True
except ImportError:
    DOCKER_SANDBOX_AVAILABLE = False

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configuration
USE_DOCKER_SANDBOX = os.environ.get("USE_DOCKER_SANDBOX", "true").lower() == "true"
DOCKER_SANDBOX_IMAGE = os.environ.get("DOCKER_SANDBOX_IMAGE", "ai-sandbox-base")
DOCKER_SANDBOX_TIMEOUT = int(os.environ.get("DOCKER_SANDBOX_TIMEOUT", "120"))
SANDBOX_TIMEOUT_SECONDS = 120


def _execute_code_in_sandbox(
    code: str,
    e2b_api_key: str | None,
    sandbox_timeout: int,
    output_format: str = "image",
    is_complex_task: bool = False,
) -> tuple:
    """
    Execute Python code in a sandbox (Docker or E2B) and return the result.

    Args:
        code: The Python code to execute
        e2b_api_key: E2B API key
        sandbox_timeout: Timeout in seconds
        output_format: The required output format (image, docx, pdf, xlsx)
        is_complex_task: Whether this is a complex task

    Returns:
        Tuple of (success, result/error_message, logs, artifacts)
    """
    effective_timeout = sandbox_timeout
    if is_complex_task:
        effective_timeout = min(sandbox_timeout * 5, SANDBOX_TIMEOUT_SECONDS)
        logger.info(f"Complex task detected, using extended timeout: {effective_timeout}s")

    if USE_DOCKER_SANDBOX and DOCKER_SANDBOX_AVAILABLE:
        logger.info("Using Docker Sandbox for execution (cost: $0)")
        return _execute_code_in_docker(code, effective_timeout, output_format)

    logger.info("Using E2B Sandbox for execution")
    return _execute_code_in_e2b(code, e2b_api_key, effective_timeout, output_format)


def _execute_code_in_docker(code: str, timeout: int, output_format: str = "image") -> tuple:
    """Execute Python code in Docker sandbox."""
    try:
        result: SandboxResult = LocalDockerSandbox.execute(
            code=code, image=DOCKER_SANDBOX_IMAGE, timeout=timeout, output_format=output_format,
        )

        docker_logs = result.logs if hasattr(result, "logs") else []
        docker_artifacts = result.artifacts if hasattr(result, "artifacts") else []

        class MockE2BResult:
            def __init__(self, logs, artifacts):
                self.logs = logs
                self.artifacts = artifacts

        mock_result = MockE2BResult(docker_logs, docker_artifacts)

        if result.success:
            return (True, mock_result, None, docker_artifacts)

        error_msg = result.error or "Unknown Docker error"
        if result.timed_out:
            error_msg = f"SANDBOX_TIMEOUT: Execution timed out after {timeout}s"

        return (False, f"ExecutionError: {error_msg}", None, None)
    except (TimeoutError, asyncio.TimeoutError) as e:
        logger.warning(f"Docker execution timeout: {e}", exc_info=True)
        e2b_api_key = os.environ.get("E2B_API_KEY")
        return _execute_code_in_e2b(code, e2b_api_key, timeout, output_format)
    except (ConnectionError, ConnectionRefusedError, OSError) as e:
        logger.warning(f"Docker execution connection error: {e}", exc_info=True)
        e2b_api_key = os.environ.get("E2B_API_KEY")
        return _execute_code_in_e2b(code, e2b_api_key, timeout, output_format)
    except Exception as e:
        logger.warning(f"Docker execution failed: {e}", exc_info=True)
        e2b_api_key = os.environ.get("E2B_API_KEY")
        return _execute_code_in_e2b(code, e2b_api_key, timeout, output_format)


def _execute_code_in_e2b(
    code: str, e2b_api_key: str | None, sandbox_timeout: int, output_format: str = "image",
) -> tuple:
    """Execute Python code in E2B sandbox (fallback)."""
    if not E2B_AVAILABLE:
        return (False, "E2B_NOT_AVAILABLE: E2B SDK not installed", None, None)

    try:
        with Sandbox(api_key=e2b_api_key) as sandbox:
            if output_format == "docx":
                sandbox.commands.run("pip install python-docx pandas")
            elif output_format == "pdf":
                sandbox.commands.run("pip install reportlab pandas")
            elif output_format == "xlsx":
                sandbox.commands.run("pip install openpyxl pandas")

            result = sandbox.run_code(code, timeout=sandbox_timeout)
            artifacts = result.artifacts if hasattr(result, "artifacts") else None
            return (True, result, None, artifacts)
    except (TimeoutError, asyncio.TimeoutError):
        error_msg = f"SANDBOX_TIMEOUT: Execution timed out after {sandbox_timeout}s"
        logger.error(f"E2B execution timeout: {error_msg}", exc_info=True)
        return (False, f"TimeoutError: {error_msg}", None, None)
    except (ConnectionError, ConnectionRefusedError) as e:
        logger.error(f"E2B connection error: {e}", exc_info=True)
        return (False, f"ConnectionError: {e!s}", None, None)
    except Exception as e:
        error_msg = str(e)
        if "Timeout" in error_msg or "timeout" in error_msg.lower():
            error_msg = f"SANDBOX_TIMEOUT: Execution timed out after {sandbox_timeout}s"
        logger.error(f"E2B execution error: {error_msg}", exc_info=True)
        return (False, f"ExecutionError: {error_msg}", None, None)


# Re-export from new modules for backward compatibility
from .data_viz import execute_data_visualization  # noqa: E402
from .document_gen import DocumentGenerator, ReportGenerator  # noqa: E402
from .task_router import TaskRouter  # noqa: E402
from .types import (  # noqa: E402
    MAX_RETRY_ATTEMPTS,
    MAX_REVIEW_ATTEMPTS,
    OutputFormat,
    TaskType,
)


# Legacy execute_task function for backward compatibility
def execute_task(
    domain: str, user_request: str, csv_data: str,
    task_type: str | None = None, output_format: str | None = None,
    few_shot_examples: list[Any] | None = None, **kwargs,
) -> dict:
    """Main entry point for executing tasks with the TaskRouter."""
    router = TaskRouter(llm_service=kwargs.get("llm_service"))
    return router.route(
        domain=domain, user_request=user_request, csv_data=csv_data,
        task_type=task_type, output_format=output_format,
        few_shot_examples=few_shot_examples, **kwargs,
    )


__all__ = [
    # Core functions
    "_execute_code_in_sandbox",
    "_execute_code_in_docker",
    "_execute_code_in_e2b",
    # Re-exported types
    "TaskType",
    "OutputFormat",
    "MAX_RETRY_ATTEMPTS",
    "MAX_REVIEW_ATTEMPTS",
    # Re-exported classes
    "TaskRouter",
    "DocumentGenerator",
    "ReportGenerator",
    # Re-exported functions
    "execute_task",
    "execute_data_visualization",
    # Configuration
    "USE_DOCKER_SANDBOX",
    "DOCKER_SANDBOX_IMAGE",
    "DOCKER_SANDBOX_TIMEOUT",
    "E2B_AVAILABLE",
    "DOCKER_SANDBOX_AVAILABLE",
]
