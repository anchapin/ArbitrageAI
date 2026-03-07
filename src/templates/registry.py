"""Template Registry and Document Generation.

Provides the TemplateRegistry for managing document templates and the generate_document
function for creating documents from structured JSON content.
"""

from typing import ClassVar

from src.templates.base_document import BaseDocumentTemplate
from src.templates.financial_summary import FinancialSummaryTemplate
from src.templates.legal_contract import LegalContractTemplate


class TemplateRegistry:
    """Registry for all document templates."""

    _templates: ClassVar[dict] = {
        "base": BaseDocumentTemplate,
        "legal_contract": LegalContractTemplate,
        "financial_summary": FinancialSummaryTemplate,
        # Add more templates here as needed
    }

    @classmethod
    def get_template(cls, template_name: str):
        """Get a template by name.

        Args:
            template_name: Name of the template to retrieve

        Returns:
            Template class or None if not found
        """
        return cls._templates.get(template_name)

    @classmethod
    def list_templates(cls) -> list:
        """List all available template names."""
        return list(cls._templates.keys())

    @classmethod
    def register_template(cls, name: str, template_class):
        """Register a new template."""
        cls._templates[name] = template_class


def generate_document(
    template_name: str,
    content_json: dict,
    csv_data: str,
    output_format: str = "docx",
    **kwargs,
) -> dict:
    """Generate a document using a template.

    Args:
        template_name: Name of the template to use
        content_json: Structured JSON content from LLM
        csv_data: CSV data as string
        output_format: Output format (docx or pdf)
        **kwargs: Additional arguments

    Returns:
        Dictionary with generation results
    """
    template_class = TemplateRegistry.get_template(template_name)
    if not template_class:
        return {"success": False, "message": f"Template '{template_name}' not found"}

    template = template_class()
    return template.generate(content_json, csv_data, output_format, **kwargs)


__all__ = [
    "generate_document",
    "TemplateRegistry",
]
