"""
Fine-Tuning Pipeline for Custom Models.

This module provides a comprehensive fine-tuning pipeline for task-specific models,
including dataset preparation, training, evaluation, A/B testing, and versioning.

Features:
- Fine-tuning data preparation from task history
- Support for OpenAI API and local Ollama fine-tuning
- Dataset builder with quality filtering
- Fine-tuned model evaluation (accuracy, cost/latency)
- A/B testing framework for model comparison
- Automated retraining on new data
- Model versioning and rollback
- Cost tracking and ROI calculation
"""

from .ab_testing import ABTestFramework, ABTestResult
from .cli import FineTuningCLI
from .cost_tracker import CostAnalysis, CostTracker
from .dataset_builder import DatasetBuilder, prepare_fine_tuning_dataset
from .model_evaluator import EvaluationResult, ModelEvaluator
from .model_registry import FinetuneJobRecord, ModelRegistry
from .ollama_fine_tuner import OllamaFineTuner
from .openai_fine_tuner import OpenAIFineTuner

__all__ = [
    "ABTestFramework",
    "ABTestResult",
    "CostAnalysis",
    "CostTracker",
    "DatasetBuilder",
    "EvaluationResult",
    "FineTuningCLI",
    "FinetuneJobRecord",
    "ModelEvaluator",
    "ModelRegistry",
    "OllamaFineTuner",
    "OpenAIFineTuner",
    "prepare_fine_tuning_dataset",
]
