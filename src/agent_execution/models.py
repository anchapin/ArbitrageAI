"""Models for Intelligent Task Routing.

This module contains dataclasses and models used by the intelligent routing system.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TaskProfile:
    """Represents a task's characteristics for ML analysis."""

    task_id: str
    domain: str
    user_request: str
    csv_headers: list[str]
    task_type: str
    output_format: str
    complexity_score: float
    estimated_time: float
    success_rate: float
    model_used: str
    retry_count: int
    review_attempts: int
    created_at: datetime
    execution_time: float | None = None
    actual_success: bool | None = None


@dataclass
class RouteDecision:
    """Represents a routing decision with confidence scores."""

    handler_type: str
    confidence: float
    reasoning: str
    estimated_performance: dict[str, float]
    fallback_handlers: list[str]
