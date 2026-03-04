"""
Task router module.

This module contains the TaskRouter class for routing tasks to appropriate
handlers based on domain and task type.
"""

import base64
import os
import re
from typing import Any, ClassVar

from src.llm_service import LLMService
from src.utils.logger import get_logger

from .types import OutputFormat, TaskType

logger = get_logger(__name__)


class TaskRouter:
    """Routes tasks to appropriate handlers based on domain and task type."""

    DOMAIN_DEFAULT_FORMAT: ClassVar[dict] = {
        "legal": OutputFormat.DOCX,
        "accounting": OutputFormat.XLSX,
        "data_analysis": OutputFormat.IMAGE,
    }

    DOCUMENT_KEYWORDS: ClassVar[list] = [
        "document", "report", "brief", "memo", "summary", "analysis report",
        "contract", "agreement", "proposal", "letter", "write", "generate document",
    ]

    SPREADSHEET_KEYWORDS: ClassVar[list] = [
        "spreadsheet", "excel", "workbook", "sheet", "table", "data table",
        "generate excel", "generate spreadsheet", "xlsx",
    ]

    VISUALIZATION_KEYWORDS: ClassVar[list] = [
        "chart", "graph", "visualize", "plot", "bar", "line", "pie", "scatter",
        "histogram", "dashboard", "visualization", "visual",
    ]

    def __init__(self, llm_service: LLMService | None = None):
        self.llm = llm_service

    def detect_task_type(
        self, user_request: str, explicit_task_type: str | None = None,
    ) -> str:
        """Detect the task type from user request."""
        if explicit_task_type and explicit_task_type != TaskType.AUTO:
            return explicit_task_type

        request_lower = user_request.lower()

        for keyword in self.DOCUMENT_KEYWORDS:
            if keyword in request_lower:
                return TaskType.DOCUMENT

        for keyword in self.SPREADSHEET_KEYWORDS:
            if keyword in request_lower:
                return TaskType.SPREADSHEET

        for keyword in self.VISUALIZATION_KEYWORDS:
            if keyword in request_lower:
                return TaskType.VISUALIZATION

        return TaskType.VISUALIZATION

    def detect_output_format(
        self, domain: str, task_type: str, explicit_format: str | None = None,
    ) -> str:
        """Detect the output format based on domain and task type."""
        if explicit_format:
            return explicit_format

        domain_lower = domain.lower().strip()

        if domain_lower == "legal":
            if task_type == TaskType.DOCUMENT:
                return OutputFormat.DOCX
            if task_type == TaskType.SPREADSHEET:
                return OutputFormat.XLSX
            return OutputFormat.IMAGE

        if domain_lower == "accounting":
            if task_type == TaskType.SPREADSHEET:
                return OutputFormat.XLSX
            if task_type == TaskType.DOCUMENT:
                return OutputFormat.PDF
            return OutputFormat.IMAGE

        return OutputFormat.IMAGE

    def route(
        self,
        domain: str,
        user_request: str,
        csv_data: str,
        task_type: str | None = None,
        output_format: str | None = None,
        few_shot_examples: list[Any] | None = None,
        **kwargs,
    ) -> dict:
        """Route the task to the appropriate handler."""
        detected_task_type = self.detect_task_type(user_request, task_type)
        detected_format = self.detect_output_format(domain, detected_task_type, output_format)

        logger.info(
            f"TaskRouter: domain={domain}, task_type={detected_task_type}, output_format={detected_format}",
        )

        is_report = any(word in user_request.lower() for word in ["report", "summary", "analysis", "executive"])

        if is_report and detected_format == OutputFormat.DOCX:
            report_type = "summary" if "summary" in user_request.lower() else "detailed"
            return self._handle_report_generation(
                domain=domain, user_request=user_request, csv_data=csv_data,
                report_type=report_type, **kwargs,
            )

        if detected_format == OutputFormat.DOCX:
            return self._handle_document_generation(
                domain=domain, user_request=user_request, csv_data=csv_data,
                output_format=OutputFormat.DOCX, **kwargs,
            )
        if detected_format == OutputFormat.XLSX:
            return self._handle_spreadsheet_generation(
                domain=domain, user_request=user_request, csv_data=csv_data,
                output_format=OutputFormat.XLSX, **kwargs,
            )
        if detected_format == OutputFormat.PDF:
            return self._handle_document_generation(
                domain=domain, user_request=user_request, csv_data=csv_data,
                output_format=OutputFormat.PDF, **kwargs,
            )
        return self._handle_visualization(
            domain=domain, user_request=user_request, csv_data=csv_data, **kwargs,
        )

    def _handle_visualization(
        self, domain: str, user_request: str, csv_data: str,
        few_shot_examples: list[Any] | None = None, **kwargs,
    ) -> dict:
        """Handle visualization tasks."""
        from .data_viz import execute_data_visualization
        return execute_data_visualization(
            csv_data=csv_data, user_request=user_request, domain=domain,
            few_shot_examples=few_shot_examples, **kwargs,
        )

    def _handle_report_generation(
        self, domain: str, user_request: str, csv_data: str,
        report_type: str = "detailed", **kwargs,
    ) -> dict:
        """Handle report generation tasks."""
        from .document_gen import ReportGenerator
        generator = ReportGenerator(domain=domain, llm_service=self.llm, report_type=report_type)
        return generator.generate_report(user_request=user_request, csv_data=csv_data, **kwargs)

    def _handle_document_generation(
        self, domain: str, user_request: str, csv_data: str,
        output_format: str = OutputFormat.DOCX, **kwargs,
    ) -> dict:
        """Handle document generation tasks."""
        from .document_gen import DocumentGenerator
        generator = DocumentGenerator(
            domain=domain, llm_service=self.llm, output_format=output_format,
        )
        return generator.generate_document(user_request=user_request, csv_data=csv_data, **kwargs)

    def _handle_spreadsheet_generation(
        self, domain: str, user_request: str, csv_data: str,
        output_format: str = OutputFormat.XLSX, **kwargs,
    ) -> dict:
        """Handle spreadsheet generation tasks."""
        first_line = csv_data.strip().split("\n")[0]
        csv_headers = [h.strip() for h in first_line.split(",")]

        llm = self.llm or LLMService()
        system_prompt = self._get_spreadsheet_system_prompt(domain)

        prompt = f"""CSV Headers: {csv_headers}
User Request: {user_request}
Domain: {domain}

Generate Python code to create an Excel spreadsheet from the data."""

        try:
            result = llm.complete(prompt=prompt, temperature=0.3, max_tokens=2000, system_prompt=system_prompt)
            code = result["content"].strip()
            code_match = re.search(r"```python\s*([\s\S]*?)\s*```", code)
            if code_match:
                code = code_match.group(1).strip()

            code_with_csv = f'csv_data = """{csv_data}"""\n\n' + code
            e2b_api_key = kwargs.get("api_key") or os.environ.get("E2B_API_KEY")
            sandbox_timeout = kwargs.get("sandbox_timeout", 120)

            from .executor import _execute_code_in_sandbox
            success, sandbox_result, _, artifacts = _execute_code_in_sandbox(
                code_with_csv, e2b_api_key, sandbox_timeout, output_format,
            )

            if success and artifacts:
                for artifact in artifacts:
                    if hasattr(artifact, "data") and hasattr(artifact, "name"):
                        if artifact.name.endswith(".xlsx"):
                            return {
                                "success": True,
                                "file_url": f"data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{base64.b64encode(artifact.data).decode('utf-8')}",
                                "file_name": artifact.name,
                                "output_format": OutputFormat.XLSX,
                                "message": "Excel spreadsheet generated successfully",
                            }

            return {"success": False, "message": "Failed to generate Excel spreadsheet", "output_format": OutputFormat.XLSX}
        except Exception as e:
            logger.error(f"Spreadsheet generation error: {e}", exc_info=True)
            return {"success": False, "message": f"Spreadsheet generation error: {e!s}", "output_format": OutputFormat.XLSX}

    def _get_spreadsheet_system_prompt(self, domain: str) -> str:
        """Get system prompt for spreadsheet generation."""
        if domain.lower() == "legal":
            return """You are an expert legal spreadsheet generator. Create a professional Excel spreadsheet."""
        if domain.lower() == "accounting":
            return """You are an expert accounting spreadsheet generator. Create a professional Excel spreadsheet."""
        return """You are an expert spreadsheet generator. Create a professional Excel spreadsheet."""


__all__ = ["TaskRouter"]
