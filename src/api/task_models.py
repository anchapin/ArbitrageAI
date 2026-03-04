"""
Task-related database models.
"""

from datetime import datetime
import logging
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_base, relationship

from .enums import ExecutionStatus, OutputType, PlanningStatus, ReviewStatus, TaskStatus

logger = logging.getLogger(__name__)
Base = declarative_base()


class Task(Base):
    """
    Core Task model - reduced to essential fields only.

    Contains only the essential information needed for task tracking,
    client management, and billing. All other concerns are delegated to
    related entities via composition.
    """

    __tablename__ = "tasks"

    # Performance indexes and unique constraints (Issue #33, #38)
    __table_args__ = (
        UniqueConstraint("stripe_session_id", name="unique_stripe_session_id"),
        UniqueConstraint("delivery_token", name="unique_delivery_token"),
        Index("idx_task_client_email", "client_email"),
        Index("idx_task_status", "status"),
        Index("idx_task_created_at", "created_at"),
        Index("idx_task_client_status", "client_email", "status"),
        Index("idx_task_status_created", "status", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Task content
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    domain = Column(String, nullable=False)

    # Status
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)

    # Billing and client
    stripe_session_id = Column(String, nullable=True, index=True)
    client_email = Column(String, nullable=True, index=True)
    amount_paid = Column(Integer, nullable=True)  # In cents
    delivery_token = Column(String, nullable=True, index=True)
    delivery_token_expires_at = Column(DateTime, nullable=True)
    delivery_token_used = Column(Boolean, default=False)

    # Profit protection
    is_high_value = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships to composed entities (one-to-one)
    execution = relationship(
        "TaskExecution",
        uselist=False,
        cascade="all, delete-orphan",
        back_populates="task",
        lazy="joined",
    )
    planning = relationship(
        "TaskPlanning",
        uselist=False,
        cascade="all, delete-orphan",
        back_populates="task",
        lazy="joined",
    )
    review = relationship(
        "TaskReview",
        uselist=False,
        cascade="all, delete-orphan",
        back_populates="task",
        lazy="joined",
    )
    arena = relationship(
        "TaskArena",
        uselist=False,
        cascade="all, delete-orphan",
        back_populates="task",
        lazy="joined",
    )
    outputs = relationship(
        "TaskOutput",
        cascade="all, delete-orphan",
        back_populates="task",
        lazy="selectin",
    )

    # Hybrid properties for backward compatibility (Issue #5)
    @hybrid_property
    def work_plan(self):
        return self.planning.plan_content if self.planning else None

    @work_plan.setter
    def work_plan(self, value):
        if not self.planning:
            self.planning = TaskPlanning()
        self.planning.plan_content = value

    @hybrid_property
    def plan_status(self):
        return self.planning.status if self.planning else None

    @plan_status.setter
    def plan_status(self, value):
        if not self.planning:
            self.planning = TaskPlanning()
        # Handle string conversion
        if isinstance(value, str):
            try:
                self.planning.status = PlanningStatus(value.upper())
            except ValueError:
                self.planning.status = PlanningStatus.PENDING
        else:
            self.planning.status = value

    @hybrid_property
    def file_content(self):
        return self.planning.file_content if self.planning else None

    @file_content.setter
    def file_content(self, value):
        if not self.planning:
            self.planning = TaskPlanning()
        self.planning.file_content = value

    @hybrid_property
    def filename(self):
        return self.planning.filename if self.planning else None

    @filename.setter
    def filename(self, value):
        if not self.planning:
            self.planning = TaskPlanning()
        self.planning.filename = value

    @hybrid_property
    def file_type(self):
        return self.planning.file_type if self.planning else None

    @file_type.setter
    def file_type(self, value):
        if not self.planning:
            self.planning = TaskPlanning()
        self.planning.file_type = value

    @hybrid_property
    def csv_data(self):
        return (
            self.planning.file_content
            if self.planning and self.planning.file_type == "csv"
            else None
        )

    @csv_data.setter
    def csv_data(self, value):
        if not self.planning:
            self.planning = TaskPlanning()
        self.planning.file_content = value
        self.planning.file_type = "csv"

    @hybrid_property
    def retry_count(self):
        return self.execution.retry_count if self.execution else 0

    @retry_count.setter
    def retry_count(self, value):
        if not self.execution:
            self.execution = TaskExecution()
        self.execution.retry_count = value

    @hybrid_property
    def execution_log(self):
        return self.execution.execution_logs if self.execution else None

    @execution_log.setter
    def execution_log(self, value):
        if not self.execution:
            self.execution = TaskExecution()
        self.execution.execution_logs = value

    @hybrid_property
    def review_feedback(self):
        return self.review.review_feedback if self.review else None

    @review_feedback.setter
    def review_feedback(self, value):
        if not self.review:
            self.review = TaskReview()
        self.review.review_feedback = value

    @hybrid_property
    def review_approved(self):
        return self.review.approved if self.review else False

    @review_approved.setter
    def review_approved(self, value):
        if not self.review:
            self.review = TaskReview()
        self.review.approved = value

    @hybrid_property
    def review_attempts(self):
        return self.review.review_attempts if self.review else 0

    @review_attempts.setter
    def review_attempts(self, value):
        if not self.review:
            self.review = TaskReview()
        self.review.review_attempts = value

    @hybrid_property
    def escalation_reason(self):
        return self.review.escalation_reason if self.review else None

    @escalation_reason.setter
    def escalation_reason(self, value):
        if not self.review:
            self.review = TaskReview()
        self.review.escalation_reason = value

    @hybrid_property
    def escalated_at(self):
        return self.review.escalated_at if self.review else None

    @escalated_at.setter
    def escalated_at(self, value):
        if not self.review:
            self.review = TaskReview()
        self.review.escalated_at = value

    @hybrid_property
    def last_error(self):
        return (
            self.review.last_error if self.review else None
        )  # Actually could be in execution or review

    @last_error.setter
    def last_error(self, value):
        if not self.review:
            self.review = TaskReview()
        self.review.last_error = value

    @hybrid_property
    def review_status(self):
        return self.review.status if self.review else None

    @review_status.setter
    def review_status(self, value):
        if not self.review:
            self.review = TaskReview()
        if isinstance(value, str):
            try:
                self.review.status = ReviewStatus(value.upper())
            except ValueError:
                self.review.status = ReviewStatus.PENDING
        else:
            self.review.status = value

    @hybrid_property
    def extracted_context(self):
        return self.planning.extracted_context if self.planning else None

    @extracted_context.setter
    def extracted_context(self, value):
        if not self.planning:
            self.planning = TaskPlanning()
        self.planning.extracted_context = value

    @hybrid_property
    def result_image_url(self):
        if not hasattr(self, "outputs") or not self.outputs:
            return None
        try:
            image_output = next(
                (o for o in self.outputs if o.output_type == OutputType.IMAGE),
                None,
            )
            return image_output.output_url if image_output else None
        except (StopIteration, AttributeError) as e:
            logger.debug(f"Failed to get result_image_url: {e}")
            return None

    @result_image_url.setter
    def result_image_url(self, value):
        if not hasattr(self, "outputs"):
            object.__setattr__(self, "outputs", [])
        existing = next(
            (o for o in self.outputs if o.output_type == OutputType.IMAGE),
            None,
        )
        if existing:
            existing.output_url = value
        elif value:
            self.outputs.append(
                TaskOutput(output_type=OutputType.IMAGE, output_url=value),
            )

    @hybrid_property
    def result_document_url(self):
        if not hasattr(self, "outputs") or not self.outputs:
            return None
        try:
            doc_output = next(
                (
                    o
                    for o in self.outputs
                    if o.output_type in {OutputType.DOCUMENT, OutputType.PDF}
                ),
                None,
            )
            return doc_output.output_url if doc_output else None
        except (StopIteration, AttributeError) as e:
            logger.debug(f"Failed to get result_document_url: {e}")
            return None

    @result_document_url.setter
    def result_document_url(self, value):
        if not hasattr(self, "outputs"):
            object.__setattr__(self, "outputs", [])
        existing = next(
            (
                o
                for o in self.outputs
                if o.output_type in {OutputType.DOCUMENT, OutputType.PDF}
            ),
            None,
        )
        if existing:
            existing.output_url = value
        elif value:
            self.outputs.append(
                TaskOutput(output_type=OutputType.DOCUMENT, output_url=value),
            )

    @hybrid_property
    def result_spreadsheet_url(self):
        if not hasattr(self, "outputs") or not self.outputs:
            return None
        try:
            sheet_output = next(
                (o for o in self.outputs if o.output_type == OutputType.SPREADSHEET),
                None,
            )
            return sheet_output.output_url if sheet_output else None
        except (StopIteration, AttributeError) as e:
            logger.debug(f"Failed to get result_spreadsheet_url: {e}")
            return None

    @result_spreadsheet_url.setter
    def result_spreadsheet_url(self, value):
        if not hasattr(self, "outputs"):
            object.__setattr__(self, "outputs", [])
        existing = next(
            (o for o in self.outputs if o.output_type == OutputType.SPREADSHEET),
            None,
        )
        if existing:
            existing.output_url = value
        elif value:
            self.outputs.append(
                TaskOutput(output_type=OutputType.SPREADSHEET, output_url=value),
            )

    def __init__(self, **kwargs):
        # List of hybrid properties that should be handled manually
        hybrid_fields = [
            "work_plan",
            "plan_status",
            "file_content",
            "filename",
            "file_type",
            "csv_data",
            "retry_count",
            "execution_log",
            "review_feedback",
            "review_approved",
            "review_attempts",
            "escalation_reason",
            "escalated_at",
            "last_error",
            "review_status",
            "extracted_context",
            "result_image_url",
            "result_document_url",
            "result_spreadsheet_url",
        ]
        hybrids = {k: kwargs.pop(k) for k in hybrid_fields if k in kwargs}
        super().__init__(**kwargs)
        for k, v in hybrids.items():
            setattr(self, k, v)

    def to_dict(self):
        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "domain": self.domain,
            "status": self.status.value
            if isinstance(self.status, TaskStatus)
            else self.status,
            "stripe_session_id": self.stripe_session_id,
            "client_email": self.client_email,
            "amount_paid": self.amount_paid,
            "amount_dollars": (self.amount_paid / 100) if self.amount_paid else None,
            "delivery_token": self.delivery_token,
            "delivery_token_expires_at": self.delivery_token_expires_at.isoformat()
            if self.delivery_token_expires_at
            else None,
            "delivery_token_used": self.delivery_token_used,
            "is_high_value": self.is_high_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        # Flattened fields for compatibility (Issue #5)
        data.update(
            {
                "work_plan": self.work_plan,
                "plan_status": self.plan_status.value
                if isinstance(self.plan_status, PlanningStatus)
                else self.plan_status,
                "file_type": self.file_type,
                "filename": self.filename,
                "csv_data": self.csv_data,
                "retry_count": self.retry_count,
                "execution_log": self.execution_log,
                "review_feedback": self.review_feedback,
                "review_approved": self.review_approved,
                "review_attempts": self.review_attempts,
                "escalation_reason": self.escalation_reason,
                "last_error": self.last_error,
                "review_status": self.review_status.value
                if isinstance(self.review_status, ReviewStatus)
                else self.review_status,
                "extracted_context": self.extracted_context,
            },
        )

        # Also include nested structure for new code
        if self.execution:
            data["execution"] = self.execution.to_dict()
        if self.planning:
            data["planning"] = self.planning.to_dict()
        if self.review:
            data["review"] = self.review.to_dict()
        if self.arena:
            data["arena"] = self.arena.to_dict()
        if self.outputs:
            data["outputs"] = [o.to_dict() for o in self.outputs]

        return data


class TaskExecution(Base):
    """Task execution state and results."""

    __tablename__ = "task_executions"
    __table_args__ = (
        Index("idx_task_executions_task_id", "task_id"),
        Index("idx_task_executions_status", "status"),
        Index("idx_task_executions_started_at", "started_at"),
        Index("idx_task_executions_completed_at", "completed_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("tasks.id"), unique=True, nullable=False, index=True)

    status = Column(
        Enum(ExecutionStatus), default=ExecutionStatus.PENDING, nullable=False, index=True,
    )
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    execution_logs = Column(JSON, nullable=True)
    sandbox_result = Column(JSON, nullable=True)
    artifacts = Column(JSON, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="execution")

    def to_dict(self):
        return {
            "status": self.status.value
            if isinstance(self.status, ExecutionStatus)
            else self.status,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }


class TaskPlanning(Base):
    """Task planning and research results."""

    __tablename__ = "task_planning"
    __table_args__ = (
        Index("idx_task_planning_task_id", "task_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("tasks.id"), unique=True, nullable=False, index=True)

    status = Column(
        Enum(PlanningStatus), default=PlanningStatus.PENDING, nullable=False,
    )
    plan_content = Column(Text, nullable=True)
    research_findings = Column(JSON, nullable=True)
    extracted_context = Column(JSON, nullable=True)

    # File uploads
    file_type = Column(String, nullable=True)
    file_content = Column(Text, nullable=True)
    filename = Column(String, nullable=True)

    plan_generated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="planning")

    def to_dict(self):
        return {
            "status": self.status.value
            if isinstance(self.status, PlanningStatus)
            else self.status,
            "plan_content": self.plan_content,
            "filename": self.filename,
            "plan_generated_at": self.plan_generated_at.isoformat()
            if self.plan_generated_at
            else None,
        }


class TaskReview(Base):
    """Task review and feedback."""

    __tablename__ = "task_reviews"
    __table_args__ = (
        Index("idx_task_reviews_task_id", "task_id"),
        Index("idx_task_reviews_status", "status"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("tasks.id"), unique=True, nullable=False, index=True)

    status = Column(Enum(ReviewStatus), default=ReviewStatus.PENDING, nullable=False, index=True)
    approved = Column(Boolean, default=False)
    review_feedback = Column(Text, nullable=True)
    review_attempts = Column(Integer, default=0)

    # Escalation
    needs_escalation = Column(Boolean, default=False)
    escalation_reason = Column(String, nullable=True)
    escalated_at = Column(DateTime, nullable=True)

    # Human review
    human_review_notes = Column(Text, nullable=True)
    human_reviewer = Column(String, nullable=True)

    reviewed_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="review")

    def to_dict(self):
        return {
            "status": self.status.value
            if isinstance(self.status, ReviewStatus)
            else self.status,
            "approved": self.approved,
            "review_feedback": self.review_feedback,
            "review_attempts": self.review_attempts,
            "needs_escalation": self.needs_escalation,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }


class TaskArena(Base):
    """Arena competition results."""

    __tablename__ = "task_arenas"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("tasks.id"), unique=True, nullable=False)

    competition_id = Column(String, nullable=True)
    winning_model = Column(String, nullable=True)
    local_score = Column(Float, nullable=True)
    cloud_score = Column(Float, nullable=True)
    profit_score = Column(Float, nullable=True)

    completed_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="arena")

    def to_dict(self):
        return {
            "winning_model": self.winning_model,
            "local_score": self.local_score,
            "cloud_score": self.cloud_score,
            "profit_score": self.profit_score,
        }


class TaskOutput(Base):
    """Task output results."""

    __tablename__ = "task_outputs"
    __table_args__ = (
        Index("idx_task_outputs_task_id", "task_id"),
        Index("idx_task_outputs_output_type", "output_type"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False, index=True)

    output_type = Column(Enum(OutputType), nullable=False, index=True)
    output_url = Column(String, nullable=True)
    output_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="outputs")

    def to_dict(self):
        return {
            "output_type": self.output_type.value
            if isinstance(self.output_type, OutputType)
            else self.output_type,
            "output_url": self.output_url,
        }


class ScheduledTask(Base):
    """Database model for scheduled tasks."""
    __tablename__ = "scheduled_tasks"
    __table_args__ = (
        Index("idx_scheduled_tasks_status", "status"),
        Index("idx_scheduled_tasks_next_run_at", "next_run_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    domain = Column(String, nullable=False)
    cron_expression = Column(String, nullable=False)
    schedule_type = Column(String, default="RECURRING", nullable=False)
    status = Column(String, default="ACTIVE", nullable=False, index=True)
    task_data = Column(Text, nullable=True)
    next_run_at = Column(DateTime, nullable=True, index=True)
    last_run_at = Column(DateTime, nullable=True)
    last_run_result = Column(String, nullable=True)
    last_run_error = Column(Text, nullable=True)
    max_runs = Column(Integer, nullable=True)
    run_count = Column(Integer, default=0)
    timezone = Column(String, default="UTC")
    avoid_peak_hours = Column(Boolean, default=True)
    batch_size = Column(Integer, default=1)
    priority = Column(Integer, default=1)
    avg_execution_time = Column(Float, default=0.0)
    success_rate = Column(Float, default=100.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


class ScheduleHistory(Base):
    """Database model for schedule execution history."""
    __tablename__ = "schedule_history"
    __table_args__ = (
        Index("idx_schedule_history_schedule_id", "schedule_id"),
        Index("idx_schedule_history_execution_start", "execution_start"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    schedule_id = Column(String, nullable=False, index=True)
    task_id = Column(String, nullable=True)
    execution_start = Column(DateTime, nullable=False, index=True)
    execution_end = Column(DateTime, nullable=True)
    status = Column(String, nullable=False)
    result = Column(Text, nullable=True)
    execution_time_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
