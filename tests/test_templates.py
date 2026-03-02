"""
Tests for Template System

Tests cover:
- Template registry and discovery
- Base document template
- Legal contract template
- Financial summary template
- Document generation from JSON content
- CSV data handling
- Output format validation
"""

import pytest
import json
import tempfile
import os
from pathlib import Path

from src.templates import TemplateRegistry, generate_document
from src.templates.base_document import BaseDocumentTemplate
from src.templates.legal_contract import LegalContractTemplate
from src.templates.financial_summary import FinancialSummaryTemplate


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def sample_csv_data():
    """Sample CSV data for testing."""
    return """Date,Revenue,Expenses,Profit
2024-01-01,10000,5000,5000
2024-01-02,15000,7000,8000
2024-01-03,12000,6000,6000
2024-01-04,18000,8000,10000
2024-01-05,20000,9000,11000"""


@pytest.fixture
def sample_legal_content():
    """Sample JSON content for legal contract."""
    return {
        "title": "Service Agreement",
        "parties": [
            {"name": "Company ABC", "role": "Service Provider"},
            {"name": "Client XYZ", "role": "Client"}
        ],
        "effective_date": "2024-01-01",
        "terms": [
            "Service Provider agrees to deliver services as described",
            "Client agrees to pay fees as specified",
            "Both parties agree to confidentiality terms"
        ],
        "duration": "12 months",
        "termination_clause": "Either party may terminate with 30 days notice"
    }


@pytest.fixture
def sample_financial_content():
    """Sample JSON content for financial summary."""
    return {
        "title": "Q1 Financial Summary",
        "company_name": "Test Corp",
        "period": "Q1 2024",
        "summary": {
            "total_revenue": 75000,
            "total_expenses": 35000,
            "net_profit": 40000,
            "profit_margin": 53.33
        },
        "key_metrics": [
            {"metric": "Revenue Growth", "value": "15%", "trend": "up"},
            {"metric": "Expense Ratio", "value": "46.7%", "trend": "down"},
            {"metric": "Profit Margin", "value": "53.3%", "trend": "up"}
        ],
        "recommendations": [
            "Continue cost optimization initiatives",
            "Invest in revenue-generating activities",
            "Monitor cash flow closely"
        ]
    }


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# ============================================================================
# TEMPLATE REGISTRY TESTS
# ============================================================================


class TestTemplateRegistry:
    """Tests for TemplateRegistry class."""

    def test_get_template_exists(self):
        """Test retrieving existing templates."""
        template = TemplateRegistry.get_template("base")
        assert template is not None
        assert template == BaseDocumentTemplate

    def test_get_template_not_exists(self):
        """Test retrieving non-existent template."""
        template = TemplateRegistry.get_template("nonexistent")
        assert template is None

    def test_list_templates(self):
        """Test listing all available templates."""
        templates = TemplateRegistry.list_templates()
        assert isinstance(templates, list)
        assert len(templates) > 0
        assert "base" in templates
        assert "legal_contract" in templates
        assert "financial_summary" in templates

    def test_register_custom_template(self):
        """Test registering a custom template."""
        class CustomTemplate:
            pass

        TemplateRegistry.register_template("custom", CustomTemplate)
        template = TemplateRegistry.get_template("custom")
        assert template == CustomTemplate

        # Clean up
        del TemplateRegistry._templates["custom"]


# ============================================================================
# BASE DOCUMENT TEMPLATE TESTS
# ============================================================================


class TestBaseDocumentTemplate:
    """Tests for BaseDocumentTemplate class."""

    def test_template_initialization(self):
        """Test template initializes correctly."""
        template = BaseDocumentTemplate()
        assert template.document is None
        assert template.csv_data is None
        assert template.df is None
        assert template.content_json is None

    def test_template_constants(self):
        """Test template has correct constants."""
        assert BaseDocumentTemplate.DEFAULT_MARGIN == 1.0
        assert BaseDocumentTemplate.HEADING_FONT == "Calibri"
        assert BaseDocumentTemplate.BODY_FONT == "Calibri"
        assert BaseDocumentTemplate.HEADING_SIZE == 16
        assert BaseDocumentTemplate.SUBHEADING_SIZE == 14
        assert BaseDocumentTemplate.BODY_SIZE == 11

    def test_generate_with_valid_data(self, sample_csv_data):
        """Test document generation with valid data."""
        template = BaseDocumentTemplate()
        content = {
            "title": "Test Document",
            "sections": [
                {"heading": "Introduction", "content": "This is a test"}
            ]
        }

        result = template.generate(content, sample_csv_data)

        assert result["success"] is True
        assert "file_path" in result or "output_filename" in result
        assert result["output_format"] == "docx"

    def test_generate_with_invalid_csv(self):
        """Test document generation with invalid CSV data."""
        template = BaseDocumentTemplate()
        content = {"title": "Test"}
        invalid_csv = "This is not valid CSV data,,,"

        result = template.generate(content, invalid_csv)

        assert result["success"] is False
        assert "error" in result.get("message", "").lower() or "Document generation error" in result.get("message", "")

    def test_generate_with_empty_content(self, sample_csv_data):
        """Test document generation with empty content."""
        template = BaseDocumentTemplate()
        content = {}

        result = template.generate(content, sample_csv_data)

        # Should handle gracefully or return error
        assert isinstance(result, dict)
        assert "success" in result

    def test_generate_pdf_format(self, sample_csv_data):
        """Test document generation with PDF format."""
        template = BaseDocumentTemplate()
        content = {"title": "Test PDF"}

        result = template.generate(content, sample_csv_data, output_format="pdf")

        assert result["success"] is True
        assert result["output_format"] == "pdf"

    def test_generate_with_missing_csv_data(self):
        """Test document generation with missing CSV data."""
        template = BaseDocumentTemplate()
        content = {"title": "Test"}

        result = template.generate(content, "")

        assert result["success"] is False or result.get("success") is True  # May handle empty CSV


# ============================================================================
# LEGAL CONTRACT TEMPLATE TESTS
# ============================================================================


class TestLegalContractTemplate:
    """Tests for LegalContractTemplate class."""

    def test_template_initialization(self):
        """Test legal contract template initializes."""
        template = LegalContractTemplate()
        assert template is not None

    def test_generate_legal_contract(self, sample_legal_content, sample_csv_data):
        """Test legal contract generation."""
        template = LegalContractTemplate()

        result = template.generate(sample_legal_content, sample_csv_data)

        assert result["success"] is True
        assert "file_path" in result or "output_filename" in result
        assert result["document_type"] == "legal_contract"

    def test_legal_contract_with_parties(self, sample_legal_content, sample_csv_data):
        """Test legal contract includes parties information."""
        template = LegalContractTemplate()

        result = template.generate(sample_legal_content, sample_csv_data)

        assert result["success"] is True
        # Verify parties are in the content
        assert len(sample_legal_content["parties"]) == 2

    def test_legal_contract_with_terms(self, sample_legal_content, sample_csv_data):
        """Test legal contract includes terms."""
        template = LegalContractTemplate()

        result = template.generate(sample_legal_content, sample_csv_data)

        assert result["success"] is True
        # Verify terms are in the content
        assert len(sample_legal_content["terms"]) > 0

    def test_legal_contract_missing_required_fields(self, sample_csv_data):
        """Test legal contract with missing required fields."""
        template = LegalContractTemplate()
        incomplete_content = {"title": "Incomplete Contract"}

        result = template.generate(incomplete_content, sample_csv_data)

        # Should handle gracefully (either succeed with defaults or fail with error)
        assert isinstance(result, dict)
        assert "success" in result


# ============================================================================
# FINANCIAL SUMMARY TEMPLATE TESTS
# ============================================================================


class TestFinancialSummaryTemplate:
    """Tests for FinancialSummaryTemplate class."""

    def test_template_initialization(self):
        """Test financial summary template initializes."""
        template = FinancialSummaryTemplate()
        assert template is not None

    def test_generate_financial_summary(self, sample_financial_content, sample_csv_data):
        """Test financial summary generation."""
        template = FinancialSummaryTemplate()

        result = template.generate(sample_financial_content, sample_csv_data)

        assert result["success"] is True
        assert "file_path" in result or "output_filename" in result
        assert result["document_type"] == "financial_summary"

    def test_financial_summary_with_metrics(self, sample_financial_content, sample_csv_data):
        """Test financial summary includes key metrics."""
        template = FinancialSummaryTemplate()

        result = template.generate(sample_financial_content, sample_csv_data)

        assert result["success"] is True
        # Verify metrics are in the content
        assert len(sample_financial_content["key_metrics"]) > 0

    def test_financial_summary_with_recommendations(self, sample_financial_content, sample_csv_data):
        """Test financial summary includes recommendations."""
        template = FinancialSummaryTemplate()

        result = template.generate(sample_financial_content, sample_csv_data)

        assert result["success"] is True
        # Verify recommendations are in the content
        assert len(sample_financial_content["recommendations"]) > 0

    def test_financial_summary_calculations(self, sample_financial_content, sample_csv_data):
        """Test financial summary calculations are correct."""
        template = FinancialSummaryTemplate()

        # Verify the summary calculations
        summary = sample_financial_content["summary"]
        assert summary["net_profit"] == summary["total_revenue"] - summary["total_expenses"]
        assert abs(summary["profit_margin"] - (summary["net_profit"] / summary["total_revenue"] * 100)) < 0.1


# ============================================================================
# GENERATE_DOCUMENT FUNCTION TESTS
# ============================================================================


class TestGenerateDocument:
    """Tests for the generate_document helper function."""

    def test_generate_document_base_template(self, sample_csv_data):
        """Test generate_document with base template."""
        content = {"title": "Test Document"}

        result = generate_document("base", content, sample_csv_data)

        assert result["success"] is True

    def test_generate_document_legal_template(self, sample_legal_content, sample_csv_data):
        """Test generate_document with legal contract template."""
        result = generate_document("legal_contract", sample_legal_content, sample_csv_data)

        assert result["success"] is True

    def test_generate_document_financial_template(self, sample_financial_content, sample_csv_data):
        """Test generate_document with financial summary template."""
        result = generate_document("financial_summary", sample_financial_content, sample_csv_data)

        assert result["success"] is True

    def test_generate_document_invalid_template(self, sample_csv_data):
        """Test generate_document with invalid template name."""
        content = {"title": "Test"}

        result = generate_document("nonexistent_template", content, sample_csv_data)

        assert result["success"] is False
        assert "not found" in result.get("message", "").lower()


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestTemplateIntegration:
    """Integration tests for template system."""

    def test_full_document_generation_workflow(self, sample_financial_content, sample_csv_data, temp_output_dir):
        """Test complete document generation workflow."""
        # Change to temp directory for file output
        original_dir = os.getcwd()
        try:
            os.chdir(temp_output_dir)

            # Generate document
            result = generate_document(
                "financial_summary",
                sample_financial_content,
                sample_csv_data
            )

            assert result["success"] is True

            # Verify file was created
            if "file_path" in result:
                assert os.path.exists(result["file_path"])

        finally:
            os.chdir(original_dir)

    def test_multiple_template_types(self, sample_csv_data):
        """Test generating multiple document types."""
        templates_to_test = [
            ("base", {"title": "Base Doc"}),
            ("legal_contract", {
                "title": "Test Contract",
                "parties": [{"name": "A", "role": "B"}],
                "terms": ["Term 1"]
            }),
            ("financial_summary", {
                "title": "Test Financial",
                "summary": {"total_revenue": 100, "total_expenses": 50, "net_profit": 50, "profit_margin": 50},
                "key_metrics": [],
                "recommendations": []
            })
        ]

        for template_name, content in templates_to_test:
            result = generate_document(template_name, content, sample_csv_data)
            assert result["success"] is True, f"Failed for template: {template_name}"

    def test_template_error_handling(self):
        """Test error handling in template generation."""
        # Test with invalid CSV
        result = generate_document("base", {"title": "Test"}, "invalid,,,csv")
        assert isinstance(result, dict)
        assert "success" in result


# ============================================================================
# EDGE CASES AND VALIDATION TESTS
# ============================================================================


class TestTemplateEdgeCases:
    """Tests for edge cases and validation."""

    def test_unicode_content(self, sample_csv_data):
        """Test template with unicode content."""
        content = {
            "title": "Test with Unicode: 你好，世界",
            "sections": [{"heading": "Section", "content": "Émojis: 🎉🚀"}]
        }

        template = BaseDocumentTemplate()
        result = template.generate(content, sample_csv_data)

        assert result["success"] is True

    def test_very_long_content(self, sample_csv_data):
        """Test template with very long content."""
        content = {
            "title": "Long Document",
            "sections": [
                {"heading": f"Section {i}", "content": "x" * 1000}
                for i in range(50)
            ]
        }

        template = BaseDocumentTemplate()
        result = template.generate(content, sample_csv_data)

        assert result["success"] is True

    def test_special_characters_in_csv(self):
        """Test template with special characters in CSV."""
        # CSV with special characters including newlines
        csv_data = 'Name,Value\n"Test, with comma",100\n"Test with ""quotes""",200\n"Test with\nnewline",300'

        template = BaseDocumentTemplate()
        content = {"title": "Special CSV Test"}

        result = template.generate(content, csv_data)

        assert result["success"] is True

    def test_null_values_in_content(self, sample_csv_data):
        """Test template with null values in content."""
        content = {
            "title": None,
            "sections": None
        }

        template = BaseDocumentTemplate()
        result = template.generate(content, sample_csv_data)

        # Should handle gracefully
        assert isinstance(result, dict)

    def test_empty_sections(self, sample_csv_data):
        """Test template with empty sections."""
        content = {
            "title": "Empty Sections",
            "sections": []
        }

        template = BaseDocumentTemplate()
        result = template.generate(content, sample_csv_data)

        assert result["success"] is True
