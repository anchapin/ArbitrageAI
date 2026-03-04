"""
Core models module - backward-compatible re-exports.

This module maintains backward compatibility by re-exporting all models
from the new modular structure. New code should import directly from
the specific model modules (task_models, user_models, etc.).
"""

# Re-export enums for backward compatibility
from .enums import (
    ArenaCompetitionStatus,
    BidStatus,
    ExecutionStatus,
    OutputType,
    PlanningStatus,
    PricingTier,
    ReviewStatus,
    TaskStatus,
)

# Re-export financial models
from .financial_models import (
    ConfidenceAdjustment,
    ConfidenceEntry,
    CostEntry,
    EscalationLog,
    LearningEntry,
    ThresholdPetition,
    VirtualWallet,
    WebhookSecret,
)

# Re-export marketplace models
from .marketplace_models import (
    ArenaCompetition,
    Bid,
    DistributedLock,
    SimulationBid,
)

# Re-export task models
from .task_models import (
    Base,
    ScheduledTask,
    ScheduleHistory,
    Task,
    TaskArena,
    TaskExecution,
    TaskOutput,
    TaskPlanning,
    TaskReview,
)

# Re-export user models
from .user_models import (
    ClientProfile,
    QuotaUsage,
    RateLimitLog,
    UserQuota,
)

# Maintain Base for backward compatibility
__all__ = [
    # Enums
    "ArenaCompetitionStatus",
    "BidStatus",
    "ExecutionStatus",
    "OutputType",
    "PlanningStatus",
    "PricingTier",
    "ReviewStatus",
    "TaskStatus",
    # Task models
    "Base",
    "Task",
    "TaskArena",
    "TaskExecution",
    "TaskOutput",
    "TaskPlanning",
    "TaskReview",
    "ScheduledTask",
    "ScheduleHistory",
    # User models
    "ClientProfile",
    "QuotaUsage",
    "RateLimitLog",
    "UserQuota",
    # Marketplace models
    "ArenaCompetition",
    "Bid",
    "DistributedLock",
    "SimulationBid",
    # Financial models
    "ConfidenceAdjustment",
    "ConfidenceEntry",
    "CostEntry",
    "EscalationLog",
    "LearningEntry",
    "ThresholdPetition",
    "VirtualWallet",
    "WebhookSecret",
]
