"""
Context Extractor and Work Plan Generator.

This module handles context extraction from files and work plan generation.
"""

from datetime import datetime, timezone
import json
from typing import Any

from src.agent_execution.file_parser import detect_file_type, parse_file
from src.llm_service import LLMService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ContextExtractor:
    """Analyzes uploaded files to extract context."""

    def __init__(self, llm_service: LLMService | None = None):
        """Initialize the context extractor."""
        self.llm = llm_service

    def extract_context(
        self,
        file_content: str | None = None,
        csv_data: str | None = None,
        filename: str | None = None,
        file_type: str | None = None,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Extract context from uploaded files."""
        context = {
            "file_info": {},
            "data_summary": {},
            "key_insights": [],
            "extraction_success": False,
            "raw_data": None,
        }

        if file_content and filename:
            parsed = parse_file(
                file_content=file_content, filename=filename, file_type=file_type,
            )

            if parsed.get("success"):
                context["file_info"] = {
                    "filename": filename,
                    "file_type": file_type or detect_file_type(filename).value,
                    "row_count": parsed.get("row_count", 0),
                    "headers": parsed.get("headers", []),
                }
                context["data_summary"] = {
                    "headers": parsed.get("headers", []),
                    "row_count": parsed.get("row_count", 0),
                    "sample_data": parsed.get("data", [])[:5] if parsed.get("data") else [],
                }
                context["raw_data"] = parsed.get("data_as_csv", "")
                context["extraction_success"] = True

                if parsed.get("extracted_text"):
                    context["extracted_text"] = parsed["extracted_text"]

        elif csv_data:
            try:
                import io

                import pandas as pd

                df = pd.read_csv(io.StringIO(csv_data))

                context["file_info"] = {
                    "filename": filename or "data.csv",
                    "file_type": "csv",
                    "row_count": len(df),
                    "headers": df.columns.tolist(),
                }
                context["data_summary"] = {
                    "headers": df.columns.tolist(),
                    "row_count": len(df),
                    "column_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
                    "numeric_columns": df.select_dtypes(include=["number"]).columns.tolist(),
                    "categorical_columns": df.select_dtypes(include=["object"]).columns.tolist(),
                    "sample_data": df.head(5).to_dict("records"),
                }
                context["raw_data"] = csv_data
                context["extraction_success"] = True

                if not df.select_dtypes(include=["number"]).empty:
                    context["key_insights"] = self._extract_basic_insights(df)

            except Exception as e:
                context["error"] = str(e)

        if self.llm and context.get("extraction_success") and (file_content or csv_data):
            enhanced_context = self._enhance_with_llm(context, domain)
            context["key_insights"] = enhanced_context.get("key_insights", context.get("key_insights", []))
            context["data_summary"]["llm_analysis"] = enhanced_context.get("analysis")

        return context

    @staticmethod
    def _extract_basic_insights(df) -> list[str]:
        """Extract basic statistical insights from the data."""
        numeric_cols = df.select_dtypes(include=["number"]).columns
        return [f"{col}: min={df[col].min()}, max={df[col].max()}, mean={df[col].mean():.2f}" for col in numeric_cols]

    def _enhance_with_llm(self, context: dict[str, Any], domain: str | None) -> dict[str, Any]:
        """Use LLM to enhance context understanding."""
        if not self.llm:
            return {}

        headers = context.get("data_summary", {}).get("headers", [])
        sample_data = context.get("data_summary", {}).get("sample_data", [])

        system_prompt = f"""You are an expert data analyst specializing in {domain or "general"} data.
Analyze the provided data structure and provide key insights."""

        prompt = f"""Data Headers: {headers}
Sample Data (first 5 rows): {sample_data}

Provide a brief analysis (2-3 sentences) and list 3-5 key insights."""

        try:
            result = self.llm.complete(prompt=prompt, temperature=0.3, max_tokens=500, system_prompt=system_prompt)
            content = result.get("content", "")
            if "{" in content and "}" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
                return json.loads(json_str)
        except (json.JSONDecodeError, Exception):  # noqa: S110 - Intentional silent failure for JSON parsing
            pass

        return {}


class WorkPlanGenerator:
    """Creates a work plan based on extracted context and user requirements."""

    def __init__(self, llm_service: LLMService | None = None):
        """Initialize the work plan generator."""
        self.llm = llm_service or LLMService()

    def create_work_plan(
        self,
        user_request: str,
        domain: str,
        extracted_context: dict[str, Any],
        task_type: str | None = None,
        output_format: str | None = None,
        client_preferences: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a comprehensive work plan."""
        context_summary = self._build_context_summary(extracted_context)

        system_prompt = f"""You are an expert project planner for {domain} tasks.
Create a detailed work plan for fulfilling the user's request.

Return ONLY a JSON object with this structure:
{{
    "title": "Brief plan title",
    "data_analysis": "Description of input data",
    "approach": "Methodology to use",
    "steps": ["Step 1", "Step 2", "Step 3"],
    "success_criteria": ["Criterion 1", "Criterion 2"],
    "potential_issues": ["Issue 1: How to handle"],
    "recommended_chart_type": "bar|line|pie|scatter|table|document" or null,
    "output_format": "image|docx|xlsx|pdf" or null,
    "style_requirements": "Specific style requirements" or null
}}"""

        preferences_section = ""
        if client_preferences and client_preferences.get("has_history"):
            prefs_summary = client_preferences.get("preferences_summary", "")
            if prefs_summary:
                preferences_section = f"\n\nClient Preferences (MUST follow):\n{prefs_summary}"

        prompt = f"""User Request: {user_request}
Domain: {domain}
Task Type: {task_type or "auto-detect"}
Output Format: {output_format or "auto-detect"}{preferences_section}

Input Data Context:
{context_summary}

Generate the work plan as JSON."""

        try:
            result = self.llm.complete(prompt=prompt, temperature=0.3, max_tokens=1500, system_prompt=system_prompt)
            content = result.get("content", "")

            if "{" in content and "}" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
                plan = json.loads(json_str)

                required = ["title", "approach", "steps", "success_criteria"]
                if all(field in plan for field in required):
                    plan["generated_at"] = datetime.now(timezone.utc).isoformat()
                    plan["domain"] = domain
                    plan["user_request"] = user_request
                    return {"success": True, "plan": plan}

            return {"success": False, "error": "Failed to parse work plan"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _build_context_summary(context: dict[str, Any]) -> str:
        """Build a text summary of the extracted context."""
        parts = []

        file_info = context.get("file_info", {})
        if file_info:
            parts.append(f"File: {file_info.get('filename', 'unknown')}")
            parts.append(f"File Type: {file_info.get('file_type', 'unknown')}")
            parts.append(f"Rows: {file_info.get('row_count', 0)}")

        data_summary = context.get("data_summary", {})
        if data_summary.get("headers"):
            parts.append(f"Columns: {', '.join(data_summary['headers'])}")

        insights = context.get("key_insights", [])
        if insights:
            parts.append("Key Insights:")
            parts.extend(f"  - {insight}" for insight in insights[:5])

        return "\n".join(parts) if parts else "No context available"
