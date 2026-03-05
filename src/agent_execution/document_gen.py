"""
Document generation module.

This module contains DocumentGenerator and ReportGenerator classes
for generating documents and reports.
"""

import base64
import json
import os
import re

from src.llm_service import LLMService
from src.utils.logger import get_logger

from .types import OutputFormat

logger = get_logger(__name__)


class DocumentGenerator:
    """Dedicated class for document generation tasks."""

    def __init__(
        self,
        domain: str = "data_analysis",
        llm_service: LLMService | None = None,
        output_format: str = OutputFormat.DOCX,
    ):
        self.domain = domain
        self.llm = llm_service or LLMService()
        self.output_format = output_format.lower()

    def generate_document(self, user_request: str, csv_data: str, **kwargs) -> dict:
        """Generate a document based on user request and CSV data."""
        first_line = csv_data.strip().split("\n")[0]
        csv_headers = [h.strip() for h in first_line.split(",")]

        system_prompt = self._build_system_prompt()

        prompt = f"""CSV Headers: {csv_headers}
User Request: {user_request}
Domain: {self.domain}
Output Format: {self.output_format}

Generate Python code to create a {self.output_format} document from the data."""

        try:
            result = self.llm.complete(prompt=prompt, temperature=0.3, max_tokens=2000, system_prompt=system_prompt)
            code = result["content"].strip()
            code_match = re.search(r"```python\s*([\s\S]*?)\s*```", code)
            if code_match:
                code = code_match.group(1).strip()

            return self._execute_generation(code, csv_data, **kwargs)
        except Exception as e:
            logger.error(f"Document generation error: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Document generation error: {e!s}",
                "output_format": self.output_format,
            }

    def _build_system_prompt(self) -> str:
        """Build domain-specific system prompt for document generation."""
        if self.domain.lower() == "legal":
            return f"""You are an expert legal document generator. Create a professional {self.output_format} document."""
        if self.domain.lower() == "accounting":
            return f"""You are an expert accounting document generator. Create a professional {self.output_format} document."""
        return f"""You are an expert document generator. Create a professional {self.output_format} document."""

    def _execute_generation(self, code: str, csv_data: str, **kwargs) -> dict:
        """Execute document generation code in sandbox."""
        code_with_csv = f'csv_data = """{csv_data}"""\n\n' + code
        e2b_api_key = kwargs.get("api_key") or os.environ.get("E2B_API_KEY")
        sandbox_timeout = kwargs.get("sandbox_timeout", 120)

        from .executor import _execute_code_in_sandbox
        success, sandbox_result, _, artifacts = _execute_code_in_sandbox(
            code_with_csv, e2b_api_key, sandbox_timeout, self.output_format,
        )

        return self._parse_result(success, sandbox_result, artifacts)

    def _parse_result(self, success: bool, sandbox_result, artifacts: list) -> dict:
        """Parse and return the generated document."""
        if success and artifacts:
            for artifact in artifacts:
                if hasattr(artifact, "data") and hasattr(artifact, "name"):
                    if artifact.name.endswith(f".{self.output_format}"):
                        mime_type = "pdf" if self.output_format == "pdf" else "vnd.openxmlformats-officedocument.wordprocessingml.document"
                        return {
                            "success": True,
                            "file_url": f"data:application/{mime_type};base64,{base64.b64encode(artifact.data).decode('utf-8')}",
                            "file_name": artifact.name,
                            "output_format": self.output_format,
                            "message": f"{self.output_format.upper()} document generated successfully",
                        }

        if success and sandbox_result and sandbox_result.logs:
            for log in sandbox_result.logs:
                if hasattr(log, "text") and log.text and "{" in log.text:
                    try:
                        json_start = log.text.find("{")
                        json_end = log.text.rfind("}") + 1
                        json_str = log.text[json_start:json_end]
                        result_data = json.loads(json_str)
                        if result_data.get("success"):
                            return {
                                "success": True,
                                "file_url": result_data.get("file_path", ""),
                                "output_format": self.output_format,
                                "message": f"{self.output_format.upper()} document generated",
                            }
                    except (json.JSONDecodeError, Exception):  # noqa: S110 - Intentional silent failure for JSON parsing
                        pass

        return {
            "success": False,
            "message": f"Failed to generate {self.output_format} document",
            "output_format": self.output_format,
        }


class ReportGenerator:
    """Dedicated class for report generation tasks."""

    def __init__(
        self,
        domain: str = "data_analysis",
        llm_service: LLMService | None = None,
        report_type: str = "detailed",
    ):
        self.domain = domain
        self.llm = llm_service or LLMService()
        self.report_type = report_type

    def generate_report(self, user_request: str, csv_data: str, **kwargs) -> dict:
        """Generate a report based on user request and CSV data."""
        first_line = csv_data.strip().split("\n")[0]
        csv_headers = [h.strip() for h in first_line.split(",")]

        system_prompt = self._build_report_system_prompt()

        prompt = f"""CSV Headers: {csv_headers}
User Request: {user_request}
Domain: {self.domain}
Report Type: {self.report_type}

Generate Python code to create a {self.report_type} report document."""

        try:
            result = self.llm.complete(prompt=prompt, temperature=0.3, max_tokens=2500, system_prompt=system_prompt)
            code = result["content"].strip()
            code_match = re.search(r"```python\s*([\s\S]*?)\s*```", code)
            if code_match:
                code = code_match.group(1).strip()

            return self._execute_generation(code, csv_data, **kwargs)
        except Exception as e:
            logger.error(f"Report generation error: {e}", exc_info=True)
            return {"success": False, "message": f"Report generation error: {e!s}"}

    def _build_report_system_prompt(self) -> str:
        """Build system prompt for report generation."""
        report_style = "executive summary" if self.report_type == "summary" else "detailed analysis"
        if self.domain.lower() == "legal":
            return f"""You are an expert legal report generator. Create a {report_style} suitable for legal use."""
        if self.domain.lower() == "accounting":
            return f"""You are an expert accounting report generator. Create a {report_style} suitable for stakeholders."""
        return f"""You are an expert report generator. Create a {report_style}."""

    def _execute_generation(self, code: str, csv_data: str, **kwargs) -> dict:
        """Execute report generation code in sandbox."""
        code_with_csv = f'csv_data = """{csv_data}"""\n\n' + code
        e2b_api_key = kwargs.get("api_key") or os.environ.get("E2B_API_KEY")
        sandbox_timeout = kwargs.get("sandbox_timeout", 120)

        from .executor import _execute_code_in_sandbox
        success, _sandbox_result, _, artifacts = _execute_code_in_sandbox(
            code_with_csv, e2b_api_key, sandbox_timeout, "docx",
        )

        if success and artifacts:
            for artifact in artifacts:
                if hasattr(artifact, "data") and hasattr(artifact, "name"):
                    if artifact.name.endswith(".docx"):
                        return {
                            "success": True,
                            "file_url": f"data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{base64.b64encode(artifact.data).decode('utf-8')}",
                            "file_name": artifact.name,
                            "output_format": "docx",
                            "report_type": self.report_type,
                            "message": f"{self.report_type.title()} report generated successfully",
                        }

        return {"success": False, "message": f"Failed to generate {self.report_type} report"}


__all__ = ["DocumentGenerator", "ReportGenerator"]
