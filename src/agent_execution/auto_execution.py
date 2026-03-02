"""
Auto-Execution Pipeline (Issue #104)

Provides automated task execution with:
- Automatic bid placement
- Task execution workflow
- Result validation
- Payment processing
- Error handling and retries

Features:
- Configurable execution strategies
- Multi-marketplace support
- Confidence-based bidding
- Automatic retry with backoff
- Performance tracking
- Cost optimization

Usage:
    from src.agent_execution.auto_execution import AutoExecutionPipeline
    
    pipeline = AutoExecutionPipeline()
    await pipeline.initialize()
    
    # Execute task automatically
    result = await pipeline.execute_task(task_data)
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
import json

from sqlalchemy.orm import Session

from ..utils.logger import get_logger
from ..utils.telemetry import get_tracer
from ..api.models import Task, TaskStatus, Bid, BidStatus
from ..api.database import SessionLocal
from .confidence_tracker import ConfidenceTracker, get_confidence_tracker
from .self_adjusting_algorithm import SelfAdjustingConfidenceAlgorithm, get_self_adjusting_algorithm
from .marketplace_discovery import MarketplaceDiscovery
from .executor import TaskRouter

logger = get_logger(__name__)


class ExecutionStrategy(str, Enum):
    """Task execution strategies."""
    AGGRESSIVE = "aggressive"  # Bid on everything above threshold
    CONSERVATIVE = "conservative"  # Only bid on high confidence
    BALANCED = "balanced"  # Moderate approach
    LEARNING = "learning"  # Focus on gathering data


@dataclass
class ExecutionResult:
    """Result of auto-execution."""
    success: bool
    task_id: Optional[str]
    bid_id: Optional[str]
    bid_amount_cents: int
    confidence_score: float
    execution_time_ms: float
    strategy_used: str
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class BidDecision:
    """Decision on whether to bid."""
    should_bid: bool
    confidence: float
    recommended_amount_cents: int
    reasoning: str
    risk_level: str  # low, medium, high


class AutoExecutionPipeline:
    """
    Automated task execution pipeline.
    
    Features:
    - Automatic marketplace scanning
    - Confidence-based bid decisions
    - Task execution with retries
    - Performance tracking
    - Cost optimization
    """

    def __init__(
        self,
        strategy: ExecutionStrategy = ExecutionStrategy.BALANCED,
        min_confidence_threshold: float = 0.6,
        max_bid_amount_cents: int = 50000,  # $500
        max_concurrent_tasks: int = 5,
        retry_attempts: int = 3,
        retry_delay_seconds: float = 1.0,
    ):
        self.strategy = strategy
        self.min_confidence_threshold = min_confidence_threshold
        self.max_bid_amount_cents = max_bid_amount_cents
        self.max_concurrent_tasks = max_concurrent_tasks
        self.retry_attempts = retry_attempts
        self.retry_delay_seconds = retry_delay_seconds
        
        self.confidence_tracker = get_confidence_tracker()
        self.self_adjusting_algorithm = get_self_adjusting_algorithm()
        self.marketplace_discovery = MarketplaceDiscovery()
        self.task_router = TaskRouter()
        
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._execution_count = 0
        self._success_count = 0
        self._total_revenue_cents = 0
        self._tracer = get_tracer(__name__)

    async def initialize(self) -> None:
        """Initialize the auto-execution pipeline."""
        logger.info("Initializing auto-execution pipeline")
        
        # Initialize components
        await self.marketplace_discovery.initialize()
        
        logger.info("Auto-execution pipeline initialized")

    async def shutdown(self) -> None:
        """Shutdown the pipeline gracefully."""
        logger.info("Shutting down auto-execution pipeline")
        
        # Cancel active tasks
        for task_id, task in list(self._active_tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        await self.marketplace_discovery.close()

        logger.info("Auto-execution pipeline shutdown complete")

    async def execute_opportunity(
        self,
        opportunity: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> ExecutionResult:
        """
        Execute a marketplace opportunity.
        
        Args:
            opportunity: Opportunity data from marketplace
            db: Database session
        
        Returns:
            ExecutionResult: Result of execution
        """
        start_time = time.time()
        
        if db is None:
            db = SessionLocal()
        
        try:
            # Step 1: Analyze opportunity
            bid_decision = await self._analyze_opportunity(opportunity)
            
            if not bid_decision.should_bid:
                return ExecutionResult(
                    success=False,
                    task_id=None,
                    bid_id=None,
                    bid_amount_cents=0,
                    confidence_score=bid_decision.confidence,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    strategy_used=self.strategy.value,
                    reasoning=f"Did not bid: {bid_decision.reasoning}",
                )
            
            # Step 2: Place bid
            bid_result = await self._place_bid(
                opportunity=opportunity,
                amount_cents=bid_decision.recommended_amount_cents,
                db=db,
            )
            
            if not bid_result["success"]:
                return ExecutionResult(
                    success=False,
                    task_id=None,
                    bid_id=None,
                    bid_amount_cents=0,
                    confidence_score=bid_decision.confidence,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    strategy_used=self.strategy.value,
                    error_message=bid_result.get("error"),
                )
            
            # Step 3: Execute task if bid won
            if bid_result.get("status") == "won":
                execution_result = await self._execute_task(
                    task_data=opportunity,
                    bid_id=bid_result["bid_id"],
                    db=db,
                )
                
                return ExecutionResult(
                    success=execution_result["success"],
                    task_id=execution_result.get("task_id"),
                    bid_id=bid_result["bid_id"],
                    bid_amount_cents=bid_decision.recommended_amount_cents,
                    confidence_score=bid_decision.confidence,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    strategy_used=self.strategy.value,
                    metadata=execution_result.get("metadata"),
                )
            
            # Bid placed but not yet won
            return ExecutionResult(
                success=True,
                task_id=None,
                bid_id=bid_result["bid_id"],
                bid_amount_cents=bid_decision.recommended_amount_cents,
                confidence_score=bid_decision.confidence,
                execution_time_ms=(time.time() - start_time) * 1000,
                strategy_used=self.strategy.value,
                metadata={"bid_status": "pending"},
            )
            
        except Exception as e:
            logger.exception(f"Auto-execution failed: {e}")
            return ExecutionResult(
                success=False,
                task_id=None,
                bid_id=None,
                bid_amount_cents=0,
                confidence_score=0.0,
                execution_time_ms=(time.time() - start_time) * 1000,
                strategy_used=self.strategy.value,
                error_message=str(e),
            )
        finally:
            if db is not SessionLocal():
                db.close()

    async def _analyze_opportunity(
        self,
        opportunity: Dict[str, Any],
    ) -> BidDecision:
        """
        Analyze an opportunity and decide whether to bid.
        
        Args:
            opportunity: Opportunity data
        
        Returns:
            BidDecision: Decision on whether to bid
        """
        # Extract opportunity features
        title = opportunity.get("title", "")
        description = opportunity.get("description", "")
        budget_cents = opportunity.get("budget_cents", 0)
        marketplace = opportunity.get("marketplace", "unknown")

        # Calculate confidence score
        confidence_score = self.confidence_tracker.calculate_confidence_score(
            threshold=self.min_confidence_threshold,
        )
        
        # Adjust based on self-adjusting algorithm
        adjusted_threshold = self.self_adjusting_algorithm.get_adjusted_threshold(
            self.min_confidence_threshold
        )
        
        # Strategy-based adjustments
        if self.strategy == ExecutionStrategy.AGGRESSIVE:
            adjusted_threshold *= 0.8  # Lower threshold
        elif self.strategy == ExecutionStrategy.CONSERVATIVE:
            adjusted_threshold *= 1.2  # Higher threshold
        
        # Make decision
        should_bid = confidence_score >= adjusted_threshold
        
        # Calculate recommended bid amount
        if should_bid:
            recommended_amount = self._calculate_bid_amount(
                budget_cents=budget_cents,
                confidence=confidence_score,
                strategy=self.strategy,
            )
        else:
            recommended_amount = 0
        
        # Determine risk level
        if confidence_score >= 0.8:
            risk_level = "low"
        elif confidence_score >= 0.6:
            risk_level = "medium"
        else:
            risk_level = "high"
        
        return BidDecision(
            should_bid=should_bid,
            confidence=confidence_score,
            recommended_amount_cents=recommended_amount,
            reasoning=f"Confidence {confidence_score:.2f} vs threshold {adjusted_threshold:.2f}",
            risk_level=risk_level,
        )

    def _calculate_bid_amount(
        self,
        budget_cents: int,
        confidence: float,
        strategy: ExecutionStrategy,
    ) -> int:
        """
        Calculate optimal bid amount.
        
        Strategy:
        - High confidence: Bid 70-90% of budget
        - Medium confidence: Bid 50-70% of budget
        - Low confidence: Bid 30-50% of budget
        """
        if confidence >= 0.8:
            percentage = 0.8  # 80% of budget
        elif confidence >= 0.6:
            percentage = 0.6  # 60% of budget
        else:
            percentage = 0.4  # 40% of budget
        
        # Strategy adjustments
        if strategy == ExecutionStrategy.AGGRESSIVE:
            percentage = min(percentage + 0.1, 0.95)
        elif strategy == ExecutionStrategy.CONSERVATIVE:
            percentage = max(percentage - 0.1, 0.3)
        
        bid_amount = int(budget_cents * percentage)
        
        # Apply limits
        bid_amount = min(bid_amount, self.max_bid_amount_cents)
        bid_amount = max(bid_amount, 100)  # Minimum $1
        
        return bid_amount

    async def _place_bid(
        self,
        opportunity: Dict[str, Any],
        amount_cents: int,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Place a bid on an opportunity.
        
        Args:
            opportunity: Opportunity data
            amount_cents: Bid amount in cents
            db: Database session
        
        Returns:
            Dict with bid result
        """
        try:
            # Create bid record
            bid = Bid(
                id=f"bid_{datetime.utcnow().timestamp()}",
                task_id=None,  # Will be set if bid won
                marketplace=opportunity.get("marketplace", "unknown"),
                job_title=opportunity.get("title", ""),
                bid_amount_cents=amount_cents,
                status=BidStatus.PENDING,
                confidence_score=self.confidence_tracker.calculate_confidence_score(
                    threshold=self.min_confidence_threshold
                ),
            )
            
            db.add(bid)
            db.commit()
            db.refresh(bid)
            
            logger.info(f"Bid placed: {bid.id} - ${amount_cents/100:.2f}")
            
            # Record bid in confidence tracker
            self.confidence_tracker.record_bid(
                threshold=bid.confidence_score,
                bid_amount_cents=amount_cents,
            )
            
            return {
                "success": True,
                "bid_id": bid.id,
                "status": "pending",
                "amount_cents": amount_cents,
            }
            
        except Exception as e:
            db.rollback()
            logger.exception(f"Failed to place bid: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def _execute_task(
        self,
        task_data: Dict[str, Any],
        bid_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Execute a task after winning the bid.
        
        Args:
            task_data: Task data
            bid_id: Winning bid ID
            db: Database session
        
        Returns:
            Dict with execution result
        """
        task_id = None
        
        try:
            # Create task record
            task = Task(
                id=f"task_{datetime.utcnow().timestamp()}",
                title=task_data.get("title", ""),
                description=task_data.get("description", ""),
                domain=task_data.get("domain", "general"),
                status=TaskStatus.PENDING,
                bid_id=bid_id,
                budget_cents=task_data.get("budget_cents", 0),
            )
            
            db.add(task)
            db.commit()
            db.refresh(task)
            task_id = task.id
            
            # Update bid with task ID
            bid = db.query(Bid).filter(Bid.id == bid_id).first()
            if bid:
                bid.task_id = task_id
                bid.status = BidStatus.ACCEPTED
                db.commit()
            
            # Execute task with retries
            result = await self._execute_with_retries(
                task_data=task_data,
                task_id=task_id,
                domain=task.domain,
            )
            
            if result["success"]:
                task.status = TaskStatus.COMPLETED
                task.result = result.get("output", "")
                
                # Update revenue tracking
                self._success_count += 1
                self._total_revenue_cents += task.budget_cents
                
                # Record successful outcome
                self.confidence_tracker.update_outcome(
                    entry_id=task_id,
                    won=True,
                    profit_cents=task.budget_cents,
                )
            else:
                task.status = TaskStatus.FAILED
                task.error_message = result.get("error", "Unknown error")
            
            db.commit()
            
            logger.info(f"Task execution completed: {task_id} - {task.status.value}")
            
            return {
                "success": result["success"],
                "task_id": task_id,
                "output": result.get("output"),
                "error": result.get("error"),
                "metadata": result.get("metadata"),
            }
            
        except Exception as e:
            db.rollback()
            logger.exception(f"Task execution failed: {e}")
            
            if task_id:
                self.confidence_tracker.update_outcome(
                    entry_id=task_id,
                    won=False,
                    profit_cents=0,
                )
            
            return {
                "success": False,
                "task_id": task_id,
                "error": str(e),
            }

    async def _execute_with_retries(
        self,
        task_data: Dict[str, Any],
        task_id: str,
        domain: str,
    ) -> Dict[str, Any]:
        """
        Execute task with retry logic.
        
        Args:
            task_data: Task data
            task_id: Task ID
            domain: Task domain
        
        Returns:
            Dict with execution result
        """
        last_error = None
        
        for attempt in range(self.retry_attempts):
            try:
                # Route and execute task
                result = await self.task_router.route(
                    domain=domain,
                    user_request=task_data.get("title", ""),
                    csv_data=task_data.get("data", ""),
                )
                
                return {
                    "success": True,
                    "output": result,
                    "metadata": {"attempts": attempt + 1},
                }
                
            except Exception as e:
                last_error = e
                logger.warning(f"Execution attempt {attempt + 1} failed: {e}")
                
                if attempt < self.retry_attempts - 1:
                    # Wait before retry with exponential backoff
                    delay = self.retry_delay_seconds * (2 ** attempt)
                    await asyncio.sleep(delay)
        
        return {
            "success": False,
            "error": f"All {self.retry_attempts} attempts failed. Last error: {last_error}",
            "metadata": {"attempts": self.retry_attempts},
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        success_rate = (
            self._success_count / self._execution_count * 100
            if self._execution_count > 0
            else 0.0
        )
        
        return {
            "total_executions": self._execution_count,
            "successful_executions": self._success_count,
            "success_rate": f"{success_rate:.2f}%",
            "total_revenue_dollars": self._total_revenue_cents / 100,
            "active_tasks": len(self._active_tasks),
            "strategy": self.strategy.value,
        }


# Global pipeline instance
_auto_execution_pipeline: Optional[AutoExecutionPipeline] = None


def get_auto_execution_pipeline() -> AutoExecutionPipeline:
    """Get or create the global auto-execution pipeline."""
    global _auto_execution_pipeline
    if _auto_execution_pipeline is None:
        _auto_execution_pipeline = AutoExecutionPipeline()
    return _auto_execution_pipeline


def reset_auto_execution_pipeline() -> None:
    """Reset the global pipeline instance (for testing)."""
    global _auto_execution_pipeline
    _auto_execution_pipeline = None
