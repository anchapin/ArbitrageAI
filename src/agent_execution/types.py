"""Task types and output formats module.

This module contains type classifications and output format definitions
for the agent execution system.
"""


class TaskType:
    """Task type classifications."""

    VISUALIZATION = "visualization"
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    AUTO = "auto"  # Auto-detect based on domain


class OutputFormat:
    """Output format types."""

    IMAGE = "image"  # PNG/JPEG charts
    DOCX = "docx"  # Word documents
    XLSX = "xlsx"  # Excel spreadsheets
    PDF = "pdf"  # PDF documents


# Configuration constants
MAX_RETRY_ATTEMPTS = 3
MAX_REVIEW_ATTEMPTS = 2

# Sandbox configuration
USE_DOCKER_SANDBOX = True
DOCKER_SANDBOX_IMAGE = "ai-sandbox-base"
DOCKER_SANDBOX_TIMEOUT = 120

__all__ = [
    "DOCKER_SANDBOX_IMAGE",
    "DOCKER_SANDBOX_TIMEOUT",
    "MAX_RETRY_ATTEMPTS",
    "MAX_REVIEW_ATTEMPTS",
    "USE_DOCKER_SANDBOX",
    "OutputFormat",
    "TaskType",
]
