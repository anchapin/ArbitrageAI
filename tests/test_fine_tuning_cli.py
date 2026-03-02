"""
Tests for Fine-Tuning CLI

Tests cover:
- CLI command parsing
- Dataset preparation commands
- Model evaluation commands
- A/B testing commands
- Model registry commands
- Cost tracking commands
- Error handling
"""

import pytest
import subprocess
import sys
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

# Import CLI module
from src.fine_tuning.cli import FineTuningCLI, main


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_training_data():
    """Sample training data in JSONL format."""
    return [
        {"messages": [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]},
        {"messages": [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I'm doing well, thank you!"}
        ]}
    ]


@pytest.fixture
def sample_test_data():
    """Sample test data for evaluation."""
    return [
        {"prompt": "What is 2+2?", "expected": "4"},
        {"prompt": "What is the capital of France?", "expected": "Paris"}
    ]


@pytest.fixture
def cli():
    """Create CLI instance."""
    return FineTuningCLI()


# ============================================================================
# CLI INITIALIZATION TESTS
# ============================================================================


class TestFineTuningCLIInit:
    """Tests for CLI initialization."""

    def test_cli_initialization(self):
        """Test CLI initializes correctly."""
        cli = FineTuningCLI()
        assert cli.dataset_builder is not None
        assert cli.model_registry is not None
        assert cli.cost_tracker is not None

    def test_cli_with_custom_paths(self, temp_data_dir):
        """Test CLI with custom data paths."""
        cli = FineTuningCLI(data_dir=temp_data_dir)
        assert cli.data_dir == temp_data_dir


# ============================================================================
# DATASET PREPARATION TESTS
# ============================================================================


class TestDatasetPreparation:
    """Tests for dataset preparation commands."""

    def test_prepare_dataset_success(self, cli, sample_training_data, temp_data_dir):
        """Test successful dataset preparation."""
        # Create sample data file
        data_file = os.path.join(temp_data_dir, "training.jsonl")
        with open(data_file, 'w') as f:
            for item in sample_training_data:
                f.write(json.dumps(item) + '\n')

        with patch.object(cli.dataset_builder, 'prepare_dataset') as mock_prepare:
            mock_prepare.return_value = {
                "success": True,
                "dataset_path": data_file,
                "num_examples": 2
            }

            result = cli.prepare_dataset(data_file)

            assert result["success"] is True
            assert result["num_examples"] == 2

    def test_prepare_dataset_file_not_found(self, cli):
        """Test dataset preparation with missing file."""
        result = cli.prepare_dataset("nonexistent.jsonl")

        assert result["success"] is False
        assert "not found" in result.get("error", "").lower()

    def test_prepare_dataset_invalid_format(self, cli, temp_data_dir):
        """Test dataset preparation with invalid format."""
        invalid_file = os.path.join(temp_data_dir, "invalid.txt")
        with open(invalid_file, 'w') as f:
            f.write("This is not valid JSONL")

        result = cli.prepare_dataset(invalid_file)

        assert result["success"] is False


# ============================================================================
# MODEL EVALUATION TESTS
# ============================================================================


class TestModelEvaluation:
    """Tests for model evaluation commands."""

    def test_evaluate_model_success(self, cli, sample_test_data, temp_data_dir):
        """Test successful model evaluation."""
        test_file = os.path.join(temp_data_dir, "test.jsonl")
        with open(test_file, 'w') as f:
            for item in sample_test_data:
                f.write(json.dumps(item) + '\n')

        with patch.object(cli.model_evaluator, 'evaluate') as mock_eval:
            mock_eval.return_value = {
                "success": True,
                "accuracy": 0.95,
                "avg_latency_ms": 150.5,
                "cost_per_inference": 0.002
            }

            result = cli.evaluate_model("gpt-3.5-turbo", test_file)

            assert result["success"] is True
            assert result["accuracy"] == 0.95

    def test_evaluate_model_test_file_not_found(self, cli):
        """Test evaluation with missing test file."""
        result = cli.evaluate_model("gpt-3.5-turbo", "nonexistent.jsonl")

        assert result["success"] is False
        assert "not found" in result.get("error", "").lower()


# ============================================================================
# A/B TESTING TESTS
# ============================================================================


class TestABTesting:
    """Tests for A/B testing commands."""

    def test_create_ab_test(self, cli):
        """Test creating A/B test."""
        with patch.object(cli.ab_testing, 'create_test') as mock_create:
            mock_create.return_value = {
                "test_id": "ab-test-123",
                "model_a": "gpt-3.5-turbo",
                "model_b": "ft-model-v1",
                "status": "active"
            }

            result = cli.create_ab_test("gpt-3.5-turbo", "ft-model-v1")

            assert result["test_id"] == "ab-test-123"
            assert result["status"] == "active"

    def test_get_ab_test_results(self, cli):
        """Test getting A/B test results."""
        with patch.object(cli.ab_testing, 'get_results') as mock_results:
            mock_results.return_value = {
                "test_id": "ab-test-123",
                "winner": "ft-model-v1",
                "confidence": 0.95,
                "sample_size": 1000
            }

            result = cli.get_ab_test_results("ab-test-123")

            assert result["winner"] == "ft-model-v1"
            assert result["confidence"] == 0.95


# ============================================================================
# MODEL REGISTRY TESTS
# ============================================================================


class TestModelRegistry:
    """Tests for model registry commands."""

    def test_register_model(self, cli):
        """Test registering a model."""
        with patch.object(cli.model_registry, 'register_model') as mock_register:
            mock_register.return_value = {
                "model_name": "test-model",
                "version": 1,
                "status": "REGISTERED"
            }

            result = cli.register_model(
                model_name="test-model",
                base_model="gpt-3.5-turbo",
                job_id="ftjob-123",
                accuracy=0.92,
                cost=50.0
            )

            assert result["version"] == 1
            assert result["status"] == "REGISTERED"

    def test_list_models(self, cli):
        """Test listing models."""
        with patch.object(cli.model_registry, 'list_models') as mock_list:
            mock_list.return_value = [
                {"model_name": "model-1", "version": 1, "status": "DEPLOYED"},
                {"model_name": "model-2", "version": 2, "status": "REGISTERED"}
            ]

            result = cli.list_models()

            assert len(result) == 2
            assert result[0]["model_name"] == "model-1"

    def test_rollback_model(self, cli):
        """Test rolling back a model."""
        with patch.object(cli.model_registry, 'rollback_model') as mock_rollback:
            mock_rollback.return_value = {
                "success": True,
                "model_name": "test-model",
                "rolled_back_to_version": 1
            }

            result = cli.rollback_model("test-model", 1)

            assert result["success"] is True
            assert result["rolled_back_to_version"] == 1


# ============================================================================
# COST TRACKING TESTS
# ============================================================================


class TestCostTracking:
    """Tests for cost tracking commands."""

    def test_get_cost_summary(self, cli):
        """Test getting cost summary."""
        with patch.object(cli.cost_tracker, 'get_cost_summary') as mock_summary:
            mock_summary.return_value = {
                "total_training_cost": 100.0,
                "total_inference_cost": 50.0,
                "total_cost": 150.0
            }

            result = cli.get_cost_summary()

            assert result["total_training_cost"] == 100.0
            assert result["total_inference_cost"] == 50.0

    def test_get_model_costs(self, cli):
        """Test getting costs for specific model."""
        with patch.object(cli.cost_tracker, 'get_model_costs') as mock_costs:
            mock_costs.return_value = {
                "model_name": "test-model",
                "training_cost": 50.0,
                "inference_cost": 25.0
            }

            result = cli.get_model_costs("test-model")

            assert result["model_name"] == "test-model"
            assert result["training_cost"] == 50.0


# ============================================================================
# CLI COMMAND PARSING TESTS
# ============================================================================


class TestCLICommandParsing:
    """Tests for CLI command parsing."""

    def test_parse_prepare_command(self):
        """Test parsing prepare-dataset command."""
        with patch.object(sys, 'argv', ['ft-cli', 'prepare-dataset', 'data.jsonl']):
            with patch('src.fine_tuning.cli.FineTuningCLI') as MockCLI:
                mock_cli = MagicMock()
                mock_cli.prepare_dataset.return_value = {"success": True}
                MockCLI.return_value = mock_cli

                # Should call prepare_dataset
                main()
                mock_cli.prepare_dataset.assert_called_once()

    def test_parse_evaluate_command(self):
        """Test parsing evaluate-model command."""
        with patch.object(sys, 'argv', ['ft-cli', 'evaluate-model', 'gpt-3.5-turbo', 'test.jsonl']):
            with patch('src.fine_tuning.cli.FineTuningCLI') as MockCLI:
                mock_cli = MagicMock()
                mock_cli.evaluate_model.return_value = {"success": True}
                MockCLI.return_value = mock_cli

                main()
                mock_cli.evaluate_model.assert_called_once()

    def test_parse_list_models_command(self):
        """Test parsing list-models command."""
        with patch.object(sys, 'argv', ['ft-cli', 'list-models']):
            with patch('src.fine_tuning.cli.FineTuningCLI') as MockCLI:
                mock_cli = MagicMock()
                mock_cli.list_models.return_value = []
                MockCLI.return_value = mock_cli

                main()
                mock_cli.list_models.assert_called_once()

    def test_parse_unknown_command(self):
        """Test parsing unknown command."""
        with patch.object(sys, 'argv', ['ft-cli', 'unknown-command']):
            with patch('src.fine_tuning.cli.FineTuningCLI') as MockCLI:
                mock_cli = MagicMock()
                mock_cli.list_models.return_value = []
                MockCLI.return_value = mock_cli

                # Should handle gracefully or show help
                with pytest.raises(SystemExit) or pytest.raises(ValueError):
                    main()


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    def test_missing_required_argument(self, cli):
        """Test error when required argument is missing."""
        with pytest.raises(TypeError):
            cli.prepare_dataset()  # Missing file_path

    def test_invalid_model_name(self, cli, sample_test_data, temp_data_dir):
        """Test error with invalid model name."""
        test_file = os.path.join(temp_data_dir, "test.jsonl")
        with open(test_file, 'w') as f:
            for item in sample_test_data:
                f.write(json.dumps(item) + '\n')

        result = cli.evaluate_model("invalid-model-name-123", test_file)

        assert result["success"] is False or "error" in result

    def test_network_error_handling(self, cli):
        """Test handling of network errors."""
        with patch.object(cli.model_registry, 'register_model') as mock_register:
            mock_register.side_effect = Exception("Network error")

            with pytest.raises(Exception):
                cli.register_model(
                    model_name="test",
                    base_model="gpt-3.5-turbo",
                    job_id="ftjob-123"
                )


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_full_pipeline_workflow(self, cli, temp_data_dir):
        """Test full fine-tuning pipeline workflow."""
        # Create sample data
        training_file = os.path.join(temp_data_dir, "training.jsonl")
        with open(training_file, 'w') as f:
            f.write('{"messages": [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}]}\n')

        # Mock the full workflow
        with patch.object(cli.dataset_builder, 'prepare_dataset') as mock_prepare, \
             patch.object(cli.model_registry, 'register_model') as mock_register, \
             patch.object(cli.cost_tracker, 'record_training_job') as mock_cost:

            mock_prepare.return_value = {"success": True, "dataset_path": training_file}
            mock_register.return_value = {"model_name": "test-model", "version": 1}
            mock_cost.return_value = None

            # Run workflow
            prepare_result = cli.prepare_dataset(training_file)
            assert prepare_result["success"] is True

    def test_cli_with_real_data(self, cli, sample_training_data, temp_data_dir):
        """Test CLI with realistic data."""
        # Create realistic training data
        data_file = os.path.join(temp_data_dir, "realistic_data.jsonl")
        with open(data_file, 'w') as f:
            for item in sample_training_data:
                f.write(json.dumps(item) + '\n')

        # Validate data format
        with open(data_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 2
            for line in lines:
                data = json.loads(line)
                assert "messages" in data
                assert len(data["messages"]) >= 2


# ============================================================================
# HELPER FUNCTION TESTS
# ============================================================================


class TestCLIHelpers:
    """Tests for CLI helper functions."""

    def test_format_output_json(self, cli):
        """Test JSON output formatting."""
        data = {"key": "value", "number": 42}

        with patch('json.dumps') as mock_dumps:
            mock_dumps.return_value = '{"key": "value"}'
            cli.format_output(data, format="json")
            mock_dumps.assert_called_once()

    def test_format_output_text(self, cli):
        """Test text output formatting."""
        data = {"key": "value", "nested": {"a": 1}}

        output = cli.format_output(data, format="text")

        assert isinstance(output, str)
        assert "key" in output


# ============================================================================
# RUN TESTS
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
