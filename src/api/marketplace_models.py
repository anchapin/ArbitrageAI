"""Marketplace-related database models."""

from datetime import datetime
from typing import TYPE_CHECKING
import logging
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

from .enums import ArenaCompetitionStatus, BidStatus

if TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeBase as Base
else:
    Base = declarative_base()

logger = logging.getLogger(__name__)


class Bid(Base):
    """Bid Model for Autonomous Job Scanning."""
    __tablename__ = "bids"
    __table_args__ = (
        UniqueConstraint("job_id", "marketplace", name="unique_bid_per_posting"),
        UniqueConstraint("marketplace", "job_id", "status", name="unique_active_bid_per_posting"),
        Index("idx_bid_posting_id", "job_id"),
        Index("idx_bid_agent_id", "marketplace"),
        Index("idx_bid_status", "status"),
        Index("idx_bid_marketplace_status", "marketplace", "status"),
        Index("idx_bid_created_at", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_title = Column(String, nullable=False)
    job_description = Column(Text, nullable=False)
    job_url = Column(String, nullable=True)
    job_id = Column(String, nullable=True)
    bid_amount = Column(Integer, nullable=False)
    proposal = Column(Text, nullable=True)
    status = Column(Enum(BidStatus), default=BidStatus.PENDING, nullable=False)
    is_suitable = Column(Boolean, default=False)
    evaluation_reasoning = Column(Text, nullable=True)
    evaluation_confidence = Column(Integer, nullable=True)
    marketplace = Column(String, nullable=True)
    skills_matched = Column(JSON, nullable=True)
    withdrawn_reason = Column(String, nullable=True)
    withdrawal_timestamp = Column(DateTime, nullable=True)
    posting_cached_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)

    def to_dict(self):
        """Convert Bid to dictionary representation.

        Returns:
            Dictionary containing bid details, status, and timestamps.
        """
        return {
            "id": self.id, "job_title": self.job_title, "job_description": self.job_description,
            "job_url": self.job_url, "job_id": self.job_id, "bid_amount": self.bid_amount,
            "bid_amount_dollars": (self.bid_amount / 100) if self.bid_amount else None,
            "proposal": self.proposal,
            "status": self.status.value if isinstance(self.status, BidStatus) else self.status,
            "is_suitable": self.is_suitable, "evaluation_reasoning": self.evaluation_reasoning,
            "evaluation_confidence": self.evaluation_confidence, "marketplace": self.marketplace,
            "skills_matched": self.skills_matched, "withdrawn_reason": self.withdrawn_reason,
            "withdrawal_timestamp": self.withdrawal_timestamp.isoformat() if self.withdrawal_timestamp else None,
            "posting_cached_at": self.posting_cached_at.isoformat() if self.posting_cached_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
        }


class ArenaCompetition(Base):
    """Agent Arena Competition Model."""
    __tablename__ = "arena_competitions"
    __table_args__ = (
        Index("idx_arena_task_id", "task_id"),
        Index("idx_arena_status", "status"),
        Index("idx_arena_created_at", "created_at"),
        Index("idx_arena_winner", "winner"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, nullable=True, index=True)
    competition_type = Column(String, nullable=False)
    status = Column(Enum(ArenaCompetitionStatus), default=ArenaCompetitionStatus.PENDING, nullable=False, index=True)
    domain = Column(String, nullable=True)
    task_revenue = Column(Integer, nullable=True)
    user_request = Column(Text, nullable=True)
    agent_a_name = Column(String, nullable=True)
    agent_a_model = Column(String, nullable=True)
    agent_a_is_local = Column(Boolean, default=False)
    agent_a_config = Column(JSON, nullable=True)
    agent_a_result = Column(JSON, nullable=True)
    agent_a_approved = Column(Boolean, default=False)
    agent_a_execution_time = Column(Integer, default=0)
    agent_a_tokens = Column(Integer, default=0)
    agent_a_cost = Column(Integer, default=0)
    agent_a_profit = Column(Integer, default=0)
    agent_b_name = Column(String, nullable=True)
    agent_b_model = Column(String, nullable=True)
    agent_b_is_local = Column(Boolean, default=False)
    agent_b_config = Column(JSON, nullable=True)
    agent_b_result = Column(JSON, nullable=True)
    agent_b_approved = Column(Boolean, default=False)
    agent_b_execution_time = Column(Integer, default=0)
    agent_b_tokens = Column(Integer, default=0)
    agent_b_cost = Column(Integer, default=0)
    agent_b_profit = Column(Integer, default=0)
    winner = Column(String, nullable=True)
    win_reason = Column(Text, nullable=True)
    winning_artifact_url = Column(String, nullable=True)
    dpo_logged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        """Convert ArenaCompetition to dictionary representation.

        Returns:
            Dictionary containing competition details, agent stats, and results.
        """
        return {
            "id": self.id, "task_id": self.task_id,
            "competition_type": self.competition_type,
            "status": self.status.value if isinstance(self.status, ArenaCompetitionStatus) else self.status,
            "domain": self.domain, "task_revenue": self.task_revenue, "user_request": self.user_request,
            "agent_a_name": self.agent_a_name, "agent_a_model": self.agent_a_model,
            "agent_a_is_local": self.agent_a_is_local, "agent_a_approved": self.agent_a_approved,
            "agent_a_execution_time": self.agent_a_execution_time, "agent_a_tokens": self.agent_a_tokens,
            "agent_a_cost": self.agent_a_cost, "agent_a_profit": self.agent_a_profit,
            "agent_b_name": self.agent_b_name, "agent_b_model": self.agent_b_model,
            "agent_b_is_local": self.agent_b_is_local, "agent_b_approved": self.agent_b_approved,
            "agent_b_execution_time": self.agent_b_execution_time, "agent_b_tokens": self.agent_b_tokens,
            "agent_b_cost": self.agent_b_cost, "agent_b_profit": self.agent_b_profit,
            "winner": self.winner, "win_reason": self.win_reason,
            "winning_artifact_url": self.winning_artifact_url, "dpo_logged": self.dpo_logged,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class DistributedLock(Base):
    """Database-backed distributed lock for cross-process synchronization."""
    __tablename__ = "distributed_locks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lock_key = Column(String, nullable=False, unique=True, index=True)
    holder_id = Column(String, nullable=False)
    acquired_at = Column(Float, nullable=False)
    expires_at = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Convert DistributedLock to dictionary representation.

        Returns:
            Dictionary containing lock key, holder, and timing information.
        """
        return {
            "id": self.id, "lock_key": self.lock_key, "holder_id": self.holder_id,
            "acquired_at": self.acquired_at, "expires_at": self.expires_at,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SimulationBid(Base):
    """Simulation Bid Model for Training Mode."""
    __tablename__ = "simulation_bids"
    __table_args__ = (
        UniqueConstraint("job_title", "job_marketplace", "created_at", name="unique_sim_bid"),
        Index("idx_simbid_marketplace", "job_marketplace"),
        Index("idx_simbid_strategy", "strategy_type"),
        Index("idx_simbid_outcome", "would_have_won"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_title = Column(String, nullable=False)
    job_description = Column(Text, nullable=True)
    job_url = Column(String, nullable=True)
    bid_amount = Column(Integer, nullable=False)
    strategy_type = Column(String, nullable=False)
    confidence = Column(Integer, nullable=True)
    would_have_won = Column(Boolean, nullable=True)
    outcome_reasoning = Column(Text, nullable=True)
    actual_outcome = Column(String, nullable=True)
    job_marketplace = Column(String, nullable=True)
    skills_matched = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    outcome_updated_at = Column(DateTime, nullable=True)

    def to_dict(self):
        """Convert SimulationBid to dictionary representation.

        Returns:
            Dictionary containing simulation bid details and outcome data.
        """
        return {
            "id": self.id, "job_title": self.job_title, "job_description": self.job_description,
            "job_url": self.job_url, "bid_amount": self.bid_amount,
            "bid_amount_dollars": (self.bid_amount / 100) if self.bid_amount else None,
            "strategy_type": self.strategy_type, "confidence": self.confidence,
            "would_have_won": self.would_have_won, "outcome_reasoning": self.outcome_reasoning,
            "actual_outcome": self.actual_outcome, "job_marketplace": self.job_marketplace,
            "skills_matched": self.skills_matched,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "outcome_updated_at": self.outcome_updated_at.isoformat() if self.outcome_updated_at else None,
        }
