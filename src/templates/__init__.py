"""Template Library for Zero-Shot Document Generation.

This module provides pre-tested Python script templates for standard deliverables.
Instead of asking the LLM to generate Python code from scratch, the system
now asks the LLM to output structured JSON content, which is then injected
into these pre-tested templates.

Benefits:
- Guarantees formatting won't throw Python errors
- Heavily reduces token usage
- Provides consistent, reliable document generation
- Easier to maintain and update templates

Usage:
    from src.templates import TemplateRegistry, generate_document

    # Get a template for legal contracts
    template = TemplateRegistry.get_template("legal_contract")

    # Generate content as JSON from LLM
    content_json = {
        "title": "Service Agreement",
        "parties": [...],
        "terms": [...]
    }

    # Inject into template and execute
    result = template.generate(content_json, csv_data)
"""

from src.templates.registry import TemplateRegistry, generate_document

__all__ = [
    "TemplateRegistry",
    "generate_document",
]
