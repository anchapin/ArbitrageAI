#!/usr/bin/env python3
"""Script to generate refactored model files."""

import os

BASE_DIR = "/home/alex/Projects/ArbitrageAI/src/api"

# Read original models.py
with open(os.path.join(BASE_DIR, "models.py"), "r") as f:
    original_content = f.read()

# Create enums.py
enums_content = '''"""
Enum definitions for API models.
"""

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
'''

with open(os.path.join(BASE_DIR, "enums.py"), "w") as f:
    f.write(enums_content)
print("Created enums.py")

# Create task_models.py - extract Task and related models
task_models_start = original_content.find("class Task(Base):")
task_models_end = original_content.find("class BidStatus(PyEnum):")

if task_models_start != -1 and task_models_end != -1:
    task_models_content = original_content[task_models_start:task_models_end].strip()
    # Add imports
    task_models_header = '''"""
Task-related database models.
"""

from datetime import datetime
import logging
import uuid

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_base, relationship

from .enums import ExecutionStatus, OutputType, PlanningStatus, ReviewStatus, TaskStatus

logger = logging.getLogger(__name__)
Base = declarative_base()


'''
    with open(os.path.join(BASE_DIR, "task_models.py"), "w") as f:
        f.write(task_models_header + task_models_content + "\n")
    print("Created task_models.py")

# Create user_models.py - extract ClientProfile, UserQuota, QuotaUsage, RateLimitLog
user_models_content = '''"""
User-related database models.
"""

from datetime import datetime
import logging
import uuid

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

from .enums import PricingTier

logger = logging.getLogger(__name__)
Base = declarative_base()


class ClientProfile(Base):
    """Client Preference Memory (Pillar 2.5 Gap)."""
    __tablename__ = "client_profiles"
    __table_args__ = (UniqueConstraint("client_email", name="unique_client_email"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_email = Column(String, nullable=False, index=True)
    preferred_colors = Column(JSON, nullable=True)
    preferred_fonts = Column(JSON, nullable=True)
    preferred_chart_types = Column(JSON, nullable=True)
    preferred_output_formats = Column(JSON, nullable=True)
    style_preferences = Column(JSON, nullable=True)
    domain_specific_preferences = Column(JSON, nullable=True)
    feedback_history = Column(JSON, nullable=True)
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)
    average_rating = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_task_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id, "client_email": self.client_email,
            "preferred_colors": self.preferred_colors,
            "preferred_fonts": self.preferred_fonts,
            "preferred_chart_types": self.preferred_chart_types,
            "preferred_output_formats": self.preferred_output_formats,
            "style_preferences": self.style_preferences,
            "domain_specific_preferences": self.domain_specific_preferences,
            "feedback_history": self.feedback_history,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "average_rating": self.average_rating,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_task_at": self.last_task_at.isoformat() if self.last_task_at else None,
        }

    def get_preferences_summary(self) -> str:
        parts = []
        if self.preferred_colors:
            parts.append(f"Preferred colors: {', '.join(self.preferred_colors)}")
        if self.preferred_fonts:
            parts.append(f"Preferred fonts: {', '.join(self.preferred_fonts)}")
        if self.preferred_chart_types:
            parts.append(f"Preferred chart types: {', '.join(self.preferred_chart_types)}")
        if self.preferred_output_formats:
            parts.append(f"Preferred output formats: {', '.join(self.preferred_output_formats)}")
        if self.style_preferences:
            for key, value in self.style_preferences.items():
                if value:
                    parts.append(f"Style: {key}")
        return " | ".join(parts) if parts else "No preferences recorded"


class UserQuota(Base):
    """User quota and rate limit configuration."""
    __tablename__ = "user_quotas"
    __table_args__ = (
        UniqueConstraint("user_id", name="unique_user_quota"),
        Index("user_id_tier_idx", "user_id", "tier"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, unique=True, index=True)
    tier = Column(Enum(PricingTier), default=PricingTier.FREE, nullable=False)
    monthly_task_limit = Column(Integer, default=10)
    monthly_api_calls_limit = Column(Integer, default=100)
    monthly_compute_minutes_limit = Column(Integer, default=60)
    rate_limit_rps = Column(Integer, default=10)
    rate_limit_burst = Column(Integer, default=50)
    billing_cycle_start = Column(DateTime, nullable=False, default=datetime.utcnow)
    billing_cycle_end = Column(DateTime, nullable=True)
    alert_threshold_percentage = Column(Integer, default=80)
    override_rate_limit = Column(Boolean, default=False)
    override_quota = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id, "user_id": self.user_id,
            "tier": self.tier.value if self.tier else None,
            "monthly_task_limit": self.monthly_task_limit,
            "monthly_api_calls_limit": self.monthly_api_calls_limit,
            "monthly_compute_minutes_limit": self.monthly_compute_minutes_limit,
            "rate_limit_rps": self.rate_limit_rps,
            "rate_limit_burst": self.rate_limit_burst,
            "billing_cycle_start": self.billing_cycle_start.isoformat() if self.billing_cycle_start else None,
            "billing_cycle_end": self.billing_cycle_end.isoformat() if self.billing_cycle_end else None,
            "alert_threshold_percentage": self.alert_threshold_percentage,
            "override_rate_limit": self.override_rate_limit,
            "override_quota": self.override_quota,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QuotaUsage(Base):
    """Monthly quota usage tracking per user."""
    __tablename__ = "quota_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "billing_month", name="unique_user_month_usage"),
        Index("user_id_month_idx", "user_id", "billing_month"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    billing_month = Column(String, nullable=False)
    task_count = Column(Integer, default=0)
    api_call_count = Column(Integer, default=0)
    compute_minutes_used = Column(Float, default=0.0)
    quota_exceeded = Column(Boolean, default=False)
    alert_sent_at_80_percent = Column(DateTime, nullable=True)
    alert_sent_at_100_percent = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id, "user_id": self.user_id, "billing_month": self.billing_month,
            "task_count": self.task_count, "api_call_count": self.api_call_count,
            "compute_minutes_used": self.compute_minutes_used,
            "quota_exceeded": self.quota_exceeded,
            "alert_sent_at_80_percent": self.alert_sent_at_80_percent.isoformat() if self.alert_sent_at_80_percent else None,
            "alert_sent_at_100_percent": self.alert_sent_at_100_percent.isoformat() if self.alert_sent_at_100_percent else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class RateLimitLog(Base):
    """Log of rate limit violations and enforcement."""
    __tablename__ = "rate_limit_logs"
    __table_args__ = (Index("user_id_timestamp_idx", "user_id", "timestamp"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    endpoint = Column(String, nullable=False)
    method = Column(String, nullable=False)
    requests_in_window = Column(Integer, nullable=False)
    rate_limit_rps = Column(Integer, nullable=False)
    exceeded = Column(Boolean, default=False)
    quota_type = Column(String, nullable=True)
    quota_used = Column(Integer, nullable=True)
    quota_limit = Column(Integer, nullable=True)
    quota_exceeded = Column(Boolean, default=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id, "user_id": self.user_id, "endpoint": self.endpoint,
            "method": self.method, "requests_in_window": self.requests_in_window,
            "rate_limit_rps": self.rate_limit_rps, "exceeded": self.exceeded,
            "quota_type": self.quota_type, "quota_used": self.quota_used,
            "quota_limit": self.quota_limit, "quota_exceeded": self.quota_exceeded,
            "status_code": self.status_code, "response_time_ms": self.response_time_ms,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
'''

with open(os.path.join(BASE_DIR, "user_models.py"), "w") as f:
    f.write(user_models_content)
print("Created user_models.py")

print("Model refactoring script completed!")
