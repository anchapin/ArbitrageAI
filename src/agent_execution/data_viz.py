"""Data visualization module.

This module contains the core data visualization execution logic.
"""

import os
import re
from typing import Any

from src.llm_service import LLMService
from src.utils.logger import get_logger

logger = get_logger(__name__)


def execute_data_visualization(
    csv_data: str,
    user_request: str,
    domain: str,
    few_shot_examples: list[Any] | None = None,
    **kwargs,
) -> dict:
    """Execute data visualization task.

    Args:
        csv_data: CSV data as string
        user_request: User's request text
        domain: Task domain
        few_shot_examples: Pre-fetched few-shot examples
        **kwargs: Additional arguments

    Returns:
        Dictionary with visualization results
    """
    # Extract headers
    first_line = csv_data.strip().split("\n")[0]
    csv_headers = [h.strip() for h in first_line.split(",")]

    # Build system prompt with few-shot examples if available
    system_prompt = _build_visualization_system_prompt(domain, few_shot_examples)

    # Build user prompt
    prompt = f"""CSV Headers: {csv_headers}
User Request: {user_request}
Domain: {domain}

Generate Python code to create a visualization from the data.
The code should:
1. Read the CSV data using pandas
2. Create an appropriate chart based on the request
3. Save it to 'output.png'
4. Print a JSON result with keys: file_path, success

Return ONLY the Python code, no markdown."""

    try:
        llm = LLMService()
        result = llm.complete(prompt=prompt, temperature=0.3, max_tokens=2000, system_prompt=system_prompt)

        code = result["content"].strip()
        code_match = re.search(r"```python\s*([\s\S]*?)\s*```", code)
        if code_match:
            code = code_match.group(1).strip()

        # Wrap with CSV data
        code_with_csv = f'csv_data = """{csv_data}"""\n\n' + code

        # Execute in sandbox
        e2b_api_key = kwargs.get("api_key") or os.environ.get("E2B_API_KEY")
        sandbox_timeout = kwargs.get("sandbox_timeout", 120)

        success, _sandbox_result, _, artifacts = _execute_code_in_sandbox(
            code_with_csv, e2b_api_key, sandbox_timeout, "image",
        )

        if success and artifacts:
            for artifact in artifacts:
                if hasattr(artifact, "data") and hasattr(artifact, "name"):
                    if artifact.name.endswith(".png"):
                        import base64
                        return {
                            "success": True,
                            "image_url": f"data:image/png;base64,{base64.b64encode(artifact.data).decode('utf-8')}",
                            "output_format": "image",
                            "message": "Visualization generated successfully",
                        }

        return {"success": False, "message": "Failed to generate visualization"}
    except Exception as e:
        logger.error(f"Visualization error: {e}", exc_info=True)
        return {"success": False, "message": f"Visualization error: {e!s}"}


def _build_visualization_system_prompt(domain: str, few_shot_examples: list[Any] | None = None) -> str:
    """Build system prompt for visualization with optional few-shot examples."""
    base_prompt = """You are an expert data visualization specialist. Create clear, professional charts."""

    if domain.lower() == "legal":
        base_prompt += " Use formal, professional styling appropriate for legal documents."
    elif domain.lower() == "accounting":
        base_prompt += " Use clear financial visualization standards with proper number formatting."

    if few_shot_examples:
        base_prompt += "\n\nHere are some examples of good visualizations:\n"
        for i, example in enumerate(few_shot_examples[:2], 1):
            if isinstance(example, dict) and "code" in example:
                base_prompt += f"\nExample {i}:\n{example['code'][:500]}...\n"

    return base_prompt


def _execute_code_in_sandbox(
    code: str,
    api_key: str | None,
    timeout: int,
    output_format: str,
):
    """Execute code in sandbox environment."""
    # Import here to avoid circular imports
    from .executor import _execute_code_in_sandbox as exec_func
    return exec_func(code, api_key, timeout, output_format)


__all__ = ["execute_data_visualization"]
