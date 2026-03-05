"""Enum definitions for API models."""

from enum import Enum as PyEnum


class TaskStatus(PyEnum):
    """Main task status."""
    PENDING = "PENDING"
    PAID = "PAID"
    PLANNING = "PLANNING"
    PROCESSING = "PROCESSING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REVIEWING = "REVIEWING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATION = "ESCALATION"


class ExecutionStatus(PyEnum):
    """Execution-specific status."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PlanningStatus(PyEnum):
    """Planning-specific status."""
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ReviewStatus(PyEnum):
    """Review-specific status."""
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


class OutputType(PyEnum):
    """Output result types."""
    IMAGE = "IMAGE"
    DOCUMENT = "DOCUMENT"
    SPREADSHEET = "SPREADSHEET"
    PDF = "PDF"
    CODE = "CODE"
    OTHER = "OTHER"


class ArenaCompetitionStatus(PyEnum):
    """Status for arena competitions."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BidStatus(PyEnum):
    """Status for job bids."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUBMITTED = "SUBMITTED"
    WON = "WON"
    LOST = "LOST"
    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"
    DUPLICATE = "DUPLICATE"


class PricingTier(PyEnum):
    """Pricing tiers for user quotas."""
    FREE = "FREE"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"
