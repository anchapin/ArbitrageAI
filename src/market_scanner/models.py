"""
Market Scanner Models.

Data classes for market scanning operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class JobPosting:
    """Represents a job posting from the marketplace."""

    title: str
    description: str
    budget: str | None = None
    skills: list[str] = field(default_factory=list)
    url: str | None = None
    posted_date: str | None = None
    client_rating: float | None = None
    client_spend: str | None = None


@dataclass
class EvaluationResult:
    """Result of evaluating a job posting."""

    is_suitable: bool
    bid_amount: int
    reasoning: str
    task_id: str | None = None
    confidence: float | None = None
    evaluated_at: datetime | None = None

    def __post_init__(self):
        if self.evaluated_at is None:
            self.evaluated_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_suitable": self.is_suitable,
            "bid_amount": self.bid_amount,
            "reasoning": self.reasoning,
            "task_id": self.task_id,
            "confidence": self.confidence,
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
        }
