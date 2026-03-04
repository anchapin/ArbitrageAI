"""
Disaster Recovery Models.

Enums and dataclasses for backup and recovery operations.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class BackupType(Enum):
    """Types of backups supported."""

    FULL = "full"
    INCREMENTAL = "incremental"
    POINT_IN_TIME = "point_in_time"


class RecoveryStatus(Enum):
    """Status of recovery operations."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackupStatus(Enum):
    """Status of backup operations."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class BackupMetadata:
    """Metadata for backup operations."""

    backup_id: str
    backup_type: BackupType
    timestamp: datetime
    size: int
    checksum: str
    location: str
    status: BackupStatus
    retention_days: int
    compression_enabled: bool
    encryption_enabled: bool
    database_version: str
    schema_version: str


@dataclass
class RecoveryPlan:
    """Recovery plan configuration."""

    plan_id: str
    name: str
    description: str
    recovery_point_objective: int  # RPO in minutes
    recovery_time_objective: int  # RTO in minutes
    backup_locations: list[str]
    priority: str  # "high", "medium", "low"
    automated: bool
    test_frequency: str  # cron expression


@dataclass
class RecoveryOperation:
    """Recovery operation tracking."""

    operation_id: str
    plan_id: str
    status: RecoveryStatus
    start_time: datetime
    end_time: datetime | None
    backup_id: str
    target_location: str
    steps_completed: list[str]
    error_message: str | None
    validation_results: dict[str, bool]
