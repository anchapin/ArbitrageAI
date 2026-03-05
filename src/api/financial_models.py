"""Financial database models."""

from datetime import datetime
import logging
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)
Base = declarative_base()


class EscalationLog(Base):
    """Escalation Log for tracking human-in-the-loop (HITL) escalations."""
    __tablename__ = "escalation_logs"
    __table_args__ = (
        UniqueConstraint("task_id", "idempotency_key", name="unique_escalation_per_task"),
        Index("idx_escalation_logs_task_id", "task_id"),
        Index("idx_escalation_logs_idempotency_key", "idempotency_key"),
        Index("idx_escalation_logs_created_at", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, nullable=False, index=True)
    reason = Column(String, nullable=False)
    error_message = Column(Text, nullable=True)
    notification_sent = Column(Boolean, default=False)
    notification_attempt_count = Column(Integer, default=0)
    last_notification_attempt_at = Column(DateTime, nullable=True)
    notification_error = Column(Text, nullable=True)
    idempotency_key = Column(String, nullable=False, index=True)
    amount_paid = Column(Integer, nullable=True)
    domain = Column(String, nullable=True)
    client_email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    def to_dict(self):
        """
        Convert EscalationLog to dictionary.

        Returns:
            Dictionary containing escalation log data with timestamps.
        """
        return {
            "id": self.id, "task_id": self.task_id, "reason": self.reason,
            "error_message": self.error_message, "notification_sent": self.notification_sent,
            "notification_attempt_count": self.notification_attempt_count,
            "last_notification_attempt_at": self.last_notification_attempt_at.isoformat() if self.last_notification_attempt_at else None,
            "notification_error": self.notification_error, "idempotency_key": self.idempotency_key,
            "amount_paid": self.amount_paid, "domain": self.domain, "client_email": self.client_email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class ThresholdPetition(Base):
    """Threshold Petition Model for Human Oversight."""
    __tablename__ = "threshold_petitions"
    __table_args__ = (
        Index("idx_petition_status", "status"),
        Index("idx_petition_created_at", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    current_threshold_cents = Column(Integer, nullable=False)
    requested_threshold_cents = Column(Integer, nullable=False)
    confidence_score = Column(Integer, nullable=True)
    win_rate = Column(Float, nullable=True)
    avg_profit_cents = Column(Integer, nullable=True)
    current_streak = Column(Integer, nullable=True)
    supporting_data = Column(JSON, nullable=True)
    status = Column(String, default="PENDING", nullable=False)
    human_decision = Column(String, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    decision_reasoning = Column(Text, nullable=True)
    telegram_message_id = Column(String, nullable=True)
    telegram_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """
        Convert ThresholdPetition to dictionary.

        Returns:
            Dictionary containing petition data with threshold values and decision info.
        """
        return {
            "id": self.id,
            "current_threshold_dollars": self.current_threshold_cents / 100,
            "current_threshold_cents": self.current_threshold_cents,
            "requested_threshold_dollars": self.requested_threshold_cents / 100,
            "requested_threshold_cents": self.requested_threshold_cents,
            "confidence_score": self.confidence_score, "win_rate": self.win_rate,
            "avg_profit_dollars": self.avg_profit_cents / 100 if self.avg_profit_cents else None,
            "avg_profit_cents": self.avg_profit_cents, "current_streak": self.current_streak,
            "supporting_data": self.supporting_data, "status": self.status,
            "human_decision": self.human_decision,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decision_reasoning": self.decision_reasoning,
            "telegram_sent_at": self.telegram_sent_at.isoformat() if self.telegram_sent_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CostEntry(Base):
    """Cost Entry Database Model."""
    __tablename__ = "cost_entries"
    __table_args__ = (
        Index("idx_cost_task_id", "task_id"),
        Index("idx_cost_bid_id", "bid_id"),
        Index("idx_cost_type", "cost_type"),
        Index("idx_cost_marketplace", "marketplace"),
        Index("idx_cost_created_at", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, nullable=True, index=True)
    bid_id = Column(String, nullable=True, index=True)
    cost_type = Column(String, nullable=False, index=True)
    cost_cents = Column(Integer, nullable=False)
    cost_dollars = Column(Float, nullable=False)
    description = Column(String, nullable=True)
    marketplace = Column(String, nullable=True, index=True)
    strategy_type = Column(String, nullable=True)
    revenue_cents = Column(Integer, nullable=True)
    revenue_dollars = Column(Float, nullable=True)
    roi_cents = Column(Integer, nullable=True)
    roi_dollars = Column(Float, nullable=True)
    roi_percentage = Column(Float, nullable=True)
    extra_metadata = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """
        Convert CostEntry to dictionary.

        Returns:
            Dictionary containing cost entry data with ROI information.
        """
        return {
            "id": self.id, "task_id": self.task_id, "bid_id": self.bid_id,
            "cost_type": self.cost_type, "cost_cents": self.cost_cents,
            "cost_dollars": self.cost_dollars, "description": self.description,
            "marketplace": self.marketplace, "strategy_type": self.strategy_type,
            "revenue_cents": self.revenue_cents, "revenue_dollars": self.revenue_dollars,
            "roi_cents": self.roi_cents, "roi_dollars": self.roi_dollars,
            "roi_percentage": self.roi_percentage, "extra_metadata": self.extra_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ConfidenceEntry(Base):
    """Confidence Entry Database Model."""
    __tablename__ = "confidence_entries"
    __table_args__ = (
        Index("idx_conf_threshold", "threshold"),
        Index("idx_conf_won", "won"),
        Index("idx_conf_created_at", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    threshold = Column(Integer, nullable=False, index=True)
    bid_amount_cents = Column(Integer, nullable=False)
    job_title = Column(String, nullable=True)
    marketplace = Column(String, nullable=True)
    won = Column(Boolean, nullable=False, index=True)
    profit_cents = Column(Integer, nullable=True)
    profit_dollars = Column(Float, nullable=True)
    confidence_score = Column(Integer, nullable=True)
    evaluation_confidence = Column(Integer, nullable=True)
    win_streak_before = Column(Integer, default=0)
    loss_streak_before = Column(Integer, default=0)
    consecutive_wins_after = Column(Integer, default=0)
    consecutive_losses_after = Column(Integer, default=0)
    strategy_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """
        Convert ConfidenceEntry to dictionary.

        Returns:
            Dictionary containing confidence entry data with streak information.
        """
        return {
            "id": self.id, "threshold": self.threshold,
            "bid_amount_dollars": self.bid_amount_cents / 100,
            "bid_amount_cents": self.bid_amount_cents, "job_title": self.job_title,
            "marketplace": self.marketplace, "won": self.won,
            "profit_dollars": self.profit_dollars, "profit_cents": self.profit_cents,
            "confidence_score": self.confidence_score,
            "evaluation_confidence": self.evaluation_confidence,
            "win_streak_before": self.win_streak_before, "loss_streak_before": self.loss_streak_before,
            "consecutive_wins_after": self.consecutive_wins_after,
            "consecutive_losses_after": self.consecutive_losses_after,
            "strategy_type": self.strategy_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ConfidenceAdjustment(Base):
    """Confidence Adjustment Database Model."""
    __tablename__ = "confidence_adjustments"
    __table_args__ = (
        Index("idx_conf_adj_reason", "adjustment_reason"),
        Index("idx_conf_adj_created_at", "created_at"),
        Index("idx_conf_adj_manual", "is_manual_override"),
    )

    id = Column(String, primary_key=True)
    old_conservatism = Column(Integer, nullable=False)
    new_conservatism = Column(Integer, nullable=False)
    adjustment_reason = Column(String, nullable=False, index=True)
    total_adjustments = Column(Integer, default=0, nullable=False)
    is_manual_override = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """
        Convert ConfidenceAdjustment to dictionary.

        Returns:
            Dictionary containing adjustment data with old/new conservatism values.
        """
        return {
            "id": self.id, "old_conservatism": self.old_conservatism,
            "new_conservatism": self.new_conservatism,
            "adjustment_reason": self.adjustment_reason,
            "total_adjustments": self.total_adjustments,
            "is_manual_override": self.is_manual_override,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class VirtualWallet(Base):
    """Virtual Wallet Database Model."""
    __tablename__ = "virtual_wallets"

    id = Column(String, primary_key=True, default="default")
    balance_cents = Column(Integer, default=0, nullable=False)
    total_spent_cents = Column(Integer, default=0, nullable=False)
    total_earned_cents = Column(Integer, default=0, nullable=False)
    budget_cap_cents = Column(Integer, default=50000, nullable=False)
    budget_reset_period = Column(String, default="weekly", nullable=False)
    budget_start_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    budget_spent_cents = Column(Integer, default=0, nullable=False)
    low_budget_threshold_percent = Column(Integer, default=25, nullable=False)
    critical_budget_threshold_percent = Column(Integer, default=10, nullable=False)
    low_budget_alert_sent = Column(Boolean, default=False, nullable=False)
    critical_budget_alert_sent = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """
        Convert VirtualWallet to dictionary.

        Returns:
            Dictionary containing wallet balance, budget info, and usage percentages.
        """
        balance_cents = self.balance_cents or 0
        total_spent_cents = self.total_spent_cents or 0
        total_earned_cents = self.total_earned_cents or 0
        budget_cap_cents = self.budget_cap_cents or 0
        budget_spent_cents = self.budget_spent_cents or 0
        budget_remaining_cents = max(0, budget_cap_cents - budget_spent_cents)
        budget_percentage_used = (budget_spent_cents / budget_cap_cents * 100) if budget_cap_cents > 0 else 0
        return {
            "id": self.id, "balance_dollars": balance_cents / 100, "balance_cents": balance_cents,
            "total_spent_dollars": total_spent_cents / 100, "total_spent_cents": total_spent_cents,
            "total_earned_dollars": total_earned_cents / 100, "total_earned_cents": total_earned_cents,
            "budget_cap_dollars": budget_cap_cents / 100, "budget_cap_cents": budget_cap_cents,
            "budget_reset_period": self.budget_reset_period,
            "budget_spent_dollars": budget_spent_cents / 100, "budget_spent_cents": budget_spent_cents,
            "budget_remaining_dollars": budget_remaining_cents / 100,
            "budget_remaining_cents": budget_remaining_cents,
            "budget_percentage_used": budget_percentage_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WebhookSecret(Base):
    """Webhook Secret Model for Stripe."""
    __tablename__ = "webhook_secrets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    secret = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """
        Convert WebhookSecret to dictionary.

        Returns:
            Dictionary containing webhook secret metadata.
        """
        return {
            "id": self.id, "name": self.name, "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class LearningEntry(Base):
    """Learning Entry Database Model."""
    __tablename__ = "learning_entries"
    __table_args__ = (
        Index("idx_learning_task", "task_id"),
        Index("idx_learning_marketplace", "marketplace"),
        Index("idx_learning_event_type", "event_type"),
        Index("idx_learning_created_at", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=True, index=True)
    predicted_profit_cents = Column(Integer, nullable=True)
    actual_profit_cents = Column(Integer, nullable=True)
    prediction_error_cents = Column(Integer, nullable=True)
    prediction_error_percentage = Column(Float, nullable=True)
    initial_confidence_score = Column(Integer, nullable=True)
    final_confidence_score = Column(Integer, nullable=True)
    confidence_adjustment = Column(Integer, nullable=True)
    strategy_type = Column(String, nullable=True)
    strategy_adjustment_type = Column(String, nullable=True)
    strategy_adjustment_reason = Column(String, nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> dict:
        """
        Convert LearningEntry to dictionary.

        Returns:
            Dictionary containing learning event data with prediction errors.
        """
        return {
            "id": self.id, "task_id": self.task_id, "event_type": self.event_type,
            "marketplace": self.marketplace, "predicted_profit_cents": self.predicted_profit_cents,
            "actual_profit_cents": self.actual_profit_cents,
            "prediction_error_cents": self.prediction_error_cents,
            "prediction_error_percentage": self.prediction_error_percentage,
            "initial_confidence_score": self.initial_confidence_score,
            "final_confidence_score": self.final_confidence_score,
            "confidence_adjustment": self.confidence_adjustment,
            "strategy_type": self.strategy_type,
            "strategy_adjustment_type": self.strategy_adjustment_type,
            "strategy_adjustment_reason": self.strategy_adjustment_reason,
            "extra_data": self.extra_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
