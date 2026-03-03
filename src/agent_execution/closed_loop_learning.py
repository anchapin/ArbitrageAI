"""
Closed-Loop Learning System

Implements continuous learning from completed job results.
After each job completion:
1. Calculate actual profit
2. Compare to predicted profit
3. Update confidence model
4. Adjust bidding strategy
5. Weekly strategy review and insights generation

Issue #106: [PHASE 5.3] CLOSED-LOOP LEARNING SYSTEM
"""

from datetime import datetime, timedelta
from enum import Enum as PyEnum
from typing import Any

from ..api.database import SessionLocal
from ..api.models import LearningEntry
from ..utils.logger import get_logger
from .confidence_tracker import ConfidenceTracker
from .self_adjusting_algorithm import AdjustmentReason, SelfAdjustingConfidenceAlgorithm

logger = get_logger(__name__)


class LearningEventType(PyEnum):
    """Types of learning events."""

    JOB_COMPLETED = "job_completed"
    PROFIT_CALCULATED = "profit_calculated"
    PREDICTION_UPDATED = "prediction_updated"
    STRATEGY_ADJUSTED = "strategy_adjusted"
    WEEKLY_REVIEW = "weekly_review"


class StrategyAdjustmentType(PyEnum):
    """Types of strategy adjustments."""

    BID_THRESHOLD = "bid_threshold"
    MARKETPLACE_FOCUS = "marketplace_focus"
    PRICING_STRATEGY = "pricing_strategy"
    RISK_TOLERANCE = "risk_tolerance"
    TIME_ALLOCATION = "time_allocation"


class ClosedLoopLearningSystem:
    """
    Closed-Loop Learning System

    Continuously learns from completed jobs to improve bidding strategy:

    1. **Profit Calculation**: After job completion, calculate actual profit
    2. **Prediction Comparison**: Compare actual vs predicted profit
    3. **Confidence Update**: Update confidence model based on accuracy
    4. **Strategy Adjustment**: Adjust bidding strategy based on patterns
    5. **Weekly Review**: Generate insights and recommendations weekly

    Features:
    - Automatic learning from job outcomes
    - Prediction accuracy tracking
    - Confidence model updates
    - Strategy adjustment recommendations
    - Weekly performance reviews
    - Marketplace-specific learning
    - Strategy-specific learning
    """

    # Configuration
    LEARNING_RATE = 0.1  # How much to adjust based on new data
    MIN_SAMPLES_FOR_ADJUSTMENT = 10  # Minimum samples before adjusting strategy
    WEEKLY_REVIEW_DAY = "monday"  # Day for weekly review

    def __init__(self):
        """Initialize closed-loop learning system."""
        self.confidence_tracker = ConfidenceTracker()
        self.adjustment_algorithm = SelfAdjustingConfidenceAlgorithm()
        self._last_weekly_review: datetime | None = None

    def record_job_completion(
        self,
        task_id: str,
        marketplace: str,
        revenue_cents: int,
        total_cost_cents: int,
        predicted_profit_cents: int,
        initial_confidence_score: int,
        strategy_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LearningEntry:
        """
        Record job completion and calculate learning metrics.

        Args:
            task_id: Task identifier
            marketplace: Marketplace platform
            revenue_cents: Actual revenue in cents
            total_cost_cents: Total cost in cents
            predicted_profit_cents: Predicted profit in cents
            initial_confidence_score: Initial confidence score (0-100)
            strategy_type: Bidding strategy used
            metadata: Additional metadata

        Returns:
            LearningEntry with learning data
        """
        # Calculate actual profit
        actual_profit_cents = revenue_cents - total_cost_cents

        # Calculate prediction error
        prediction_error_cents = actual_profit_cents - predicted_profit_cents
        prediction_error_percentage = (
            (prediction_error_cents / predicted_profit_cents * 100)
            if predicted_profit_cents != 0
            else 0
        )

        # Update confidence tracker
        won = actual_profit_cents > 0
        try:
            self.confidence_tracker.update_outcome(
                entry_id=task_id,
                won=won,
                profit_cents=actual_profit_cents,
            )
        except Exception as e:
            logger.warning(f"Could not update confidence tracker: {e}")

        # Calculate new confidence score
        try:
            new_confidence_score = self.confidence_tracker.calculate_confidence_score(
                threshold=50,
            )
        except Exception as e:
            logger.warning(f"Failed to calculate confidence score: {e}")
            new_confidence_score = initial_confidence_score

        confidence_adjustment = new_confidence_score - initial_confidence_score

        # Create learning entry
        db = SessionLocal()
        try:
            import uuid

            entry = LearningEntry(
                id=str(uuid.uuid4()),
                task_id=task_id,
                event_type=LearningEventType.JOB_COMPLETED.value,
                marketplace=marketplace,
                predicted_profit_cents=predicted_profit_cents,
                actual_profit_cents=actual_profit_cents,
                prediction_error_cents=prediction_error_cents,
                prediction_error_percentage=prediction_error_percentage,
                initial_confidence_score=initial_confidence_score,
                final_confidence_score=new_confidence_score,
                confidence_adjustment=confidence_adjustment,
                strategy_type=strategy_type,
                extra_data=metadata,
            )

            db.add(entry)
            db.commit()
            db.refresh(entry)

            logger.info(
                f"Recorded job completion - Task: {task_id}, "
                f"Actual Profit: ${actual_profit_cents / 100:.2f}, "
                f"Prediction Error: {prediction_error_percentage:.1f}%",
            )

            # Trigger strategy adjustment if needed
            self._maybe_adjust_strategy(marketplace, strategy_type)

            # Check if weekly review is needed
            self._maybe_trigger_weekly_review()

            return entry

        except Exception as e:
            logger.error(f"Failed to record job completion: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    def calculate_prediction_accuracy(
        self,
        marketplace: str | None = None,
        strategy_type: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Calculate prediction accuracy metrics.

        Args:
            marketplace: Filter by marketplace
            strategy_type: Filter by strategy type
            limit: Number of entries to analyze

        Returns:
            Dictionary with accuracy metrics
        """
        db = SessionLocal()
        try:
            query = db.query(LearningEntry).filter(
                LearningEntry.event_type == LearningEventType.JOB_COMPLETED.value,
            )

            if marketplace:
                query = query.filter(LearningEntry.marketplace == marketplace)
            if strategy_type:
                query = query.filter(LearningEntry.strategy_type == strategy_type)

            query = query.order_by(LearningEntry.created_at.desc()).limit(limit)
            entries = query.all()

            if not entries:
                return {"error": "No learning entries found"}

            # Calculate metrics
            total_entries = len(entries)
            accurate_predictions = sum(
                1
                for e in entries
                if abs(e.prediction_error_percentage or 0) <= 20  # Within 20%
            )
            overestimates = sum(1 for e in entries if e.prediction_error_cents < 0)
            underestimates = sum(1 for e in entries if e.prediction_error_cents > 0)

            avg_error = (
                sum(abs(e.prediction_error_cents or 0) for e in entries) / total_entries
            )
            avg_error_pct = (
                sum(abs(e.prediction_error_percentage or 0) for e in entries)
                / total_entries
            )

            total_predicted = sum(e.predicted_profit_cents or 0 for e in entries)
            total_actual = sum(e.actual_profit_cents or 0 for e in entries)

            return {
                "total_entries": total_entries,
                "accuracy_rate": (accurate_predictions / total_entries * 100)
                if total_entries > 0
                else 0,
                "overestimate_rate": (overestimates / total_entries * 100)
                if total_entries > 0
                else 0,
                "underestimate_rate": (underestimates / total_entries * 100)
                if total_entries > 0
                else 0,
                "average_error_cents": avg_error,
                "average_error_dollars": avg_error / 100,
                "average_error_percentage": avg_error_pct,
                "total_predicted_profit_cents": total_predicted,
                "total_actual_profit_cents": total_actual,
                "total_predicted_profit_dollars": total_predicted / 100,
                "total_actual_profit_dollars": total_actual / 100,
                "profit_variance_cents": total_actual - total_predicted,
                "profit_variance_dollars": (total_actual - total_predicted) / 100,
            }

        except Exception as e:
            logger.error(f"Failed to calculate prediction accuracy: {e}")
            raise
        finally:
            db.close()

    def get_learning_insights(
        self,
        marketplace: str | None = None,
        strategy_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate learning insights and recommendations.

        Args:
            marketplace: Filter by marketplace
            strategy_type: Filter by strategy type

        Returns:
            Dictionary with insights and recommendations
        """
        accuracy = self.calculate_prediction_accuracy(
            marketplace=marketplace, strategy_type=strategy_type,
        )

        if "error" in accuracy:
            return accuracy

        insights = []
        recommendations = []

        # Analyze prediction accuracy
        if accuracy["accuracy_rate"] < 70:
            insights.append(
                f"Prediction accuracy is low ({accuracy['accuracy_rate']:.1f}%). "
                "Consider adjusting profit estimation model.",
            )
            recommendations.append(
                "Review cost estimation factors and add more granular tracking",
            )

        # Analyze bias
        if accuracy["overestimate_rate"] > 60:
            insights.append(
                f"Tendency to overestimate profits ({accuracy['overestimate_rate']:.1f}% of cases). "
                "Predictions are consistently optimistic.",
            )
            recommendations.append(
                "Apply conservative adjustment factor (-10% to -20%) to predictions",
            )
        elif accuracy["underestimate_rate"] > 60:
            insights.append(
                f"Tendency to underestimate profits ({accuracy['underestimate_rate']:.1f}% of cases). "
                "Missing profitable opportunities.",
            )
            recommendations.append(
                "Review cost factors - may be overestimating expenses",
            )

        # Analyze variance
        variance_pct = (
            (accuracy["profit_variance_cents"] / accuracy["total_predicted_profit_cents"] * 100)
            if accuracy["total_predicted_profit_cents"] > 0
            else 0
        )
        if abs(variance_pct) > 30:
            insights.append(
                f"High profit variance ({variance_pct:.1f}%). "
                "Actual profits differ significantly from predictions.",
            )
            recommendations.append(
                "Improve cost tracking and add contingency buffers",
            )

        return {
            "insights": insights,
            "recommendations": recommendations,
            "accuracy_metrics": accuracy,
            "confidence_score": self.confidence_tracker.calculate_confidence_score(50),
        }

    def perform_weekly_review(self) -> dict[str, Any]:
        """
        Perform weekly strategy review.

        Analyzes past week's performance and generates strategic recommendations.

        Returns:
            Dictionary with review results and recommendations
        """
        db = SessionLocal()
        try:
            # Get entries from past week
            week_ago = datetime.utcnow() - timedelta(days=7)

            entries = (
                db.query(LearningEntry)
                .filter(
                    LearningEntry.created_at >= week_ago,
                    LearningEntry.event_type == LearningEventType.JOB_COMPLETED.value,
                )
                .all()
            )

            if not entries:
                return {"status": "no_data", "message": "No jobs completed this week"}

            # Aggregate by marketplace
            marketplace_stats = {}
            strategy_stats = {}

            for entry in entries:
                # Marketplace stats
                mp = entry.marketplace or "unknown"
                if mp not in marketplace_stats:
                    marketplace_stats[mp] = {
                        "total_jobs": 0,
                        "total_profit_cents": 0,
                        "total_predicted_cents": 0,
                        "accurate_predictions": 0,
                    }

                marketplace_stats[mp]["total_jobs"] += 1
                marketplace_stats[mp]["total_profit_cents"] += (
                    entry.actual_profit_cents or 0
                )
                marketplace_stats[mp]["total_predicted_cents"] += (
                    entry.predicted_profit_cents or 0
                )
                if abs(entry.prediction_error_percentage or 0) <= 20:
                    marketplace_stats[mp]["accurate_predictions"] += 1

                # Strategy stats
                strategy = entry.strategy_type or "unknown"
                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {
                        "total_jobs": 0,
                        "total_profit_cents": 0,
                        "win_rate": 0,
                        "wins": 0,
                    }

                strategy_stats[strategy]["total_jobs"] += 1
                if (entry.actual_profit_cents or 0) > 0:
                    strategy_stats[strategy]["wins"] += 1
                    strategy_stats[strategy]["total_profit_cents"] += (
                        entry.actual_profit_cents or 0
                    )

            # Calculate rates
            for mp in marketplace_stats.values():
                mp["accuracy_rate"] = (
                    mp["accurate_predictions"] / mp["total_jobs"] * 100
                )
                mp["total_profit_dollars"] = mp["total_profit_cents"] / 100
                mp["prediction_accuracy_dollars"] = (
                    mp["total_predicted_cents"] / 100
                )

            for strategy in strategy_stats.values():
                strategy["win_rate"] = (
                    strategy["wins"] / strategy["total_jobs"] * 100
                )
                strategy["total_profit_dollars"] = strategy["total_profit_cents"] / 100

            # Generate recommendations
            recommendations = []

            # Best performing marketplace
            if marketplace_stats:
                best_mp = max(
                    marketplace_stats.items(),
                    key=lambda x: x[1]["total_profit_cents"],
                )
                recommendations.append(
                    f"Focus on {best_mp[0]} marketplace - highest profit generator "
                    f"(${best_mp[1]['total_profit_dollars']:.2f} this week)",
                )

            # Best performing strategy
            if strategy_stats:
                best_strategy = max(
                    strategy_stats.items(),
                    key=lambda x: x[1]["win_rate"],
                )
                recommendations.append(
                    f"Use {best_strategy[0]} strategy - highest win rate "
                    f"({best_strategy[1]['win_rate']:.1f}%)",
                )

            # Create weekly review entry
            import uuid

            review_entry = LearningEntry(
                id=str(uuid.uuid4()),
                task_id=f"weekly_review_{datetime.utcnow().strftime('%Y-%m-%d')}",
                event_type=LearningEventType.WEEKLY_REVIEW.value,
                marketplace="all",
                extra_data={
                    "marketplace_stats": marketplace_stats,
                    "strategy_stats": strategy_stats,
                    "total_jobs": len(entries),
                    "review_period_days": 7,
                },
            )

            db.add(review_entry)
            db.commit()

            self._last_weekly_review = datetime.utcnow()

            logger.info(
                f"Weekly review completed - {len(entries)} jobs analyzed, "
                f"{len(recommendations)} recommendations generated",
            )

            return {
                "status": "success",
                "review_date": datetime.utcnow().isoformat(),
                "total_jobs_analyzed": len(entries),
                "marketplace_performance": marketplace_stats,
                "strategy_performance": strategy_stats,
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.error(f"Failed to perform weekly review: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    def _maybe_adjust_strategy(
        self,
        marketplace: str,
        strategy_type: str | None,
    ) -> None:
        """
        Adjust strategy if enough data has been collected.

        Args:
            marketplace: Marketplace platform
            strategy_type: Strategy type
        """
        # Check if we have enough samples
        db = SessionLocal()
        try:
            count = (
                db.query(LearningEntry)
                .filter(
                    LearningEntry.marketplace == marketplace,
                    LearningEntry.event_type == LearningEventType.JOB_COMPLETED.value,
                )
                .count()
            )

            if count >= self.MIN_SAMPLES_FOR_ADJUSTMENT:
                # Get recent accuracy
                accuracy = self.calculate_prediction_accuracy(
                    marketplace=marketplace, limit=50,
                )

                # Adjust if accuracy is poor
                if accuracy.get("accuracy_rate", 100) < 60:
                    logger.info(
                        f"Triggering strategy adjustment for {marketplace} - "
                        f"accuracy rate {accuracy['accuracy_rate']:.1f}%",
                    )

                    self.adjustment_algorithm.adjust_conservatism(
                        reason=AdjustmentReason.POOR_PERFORMANCE,
                    )

                    # Record adjustment
                    entry = LearningEntry(
                        id=str(id),
                        task_id=f"adjustment_{marketplace}_{datetime.utcnow().strftime('%Y-%m-%d')}",
                        event_type=LearningEventType.STRATEGY_ADJUSTED.value,
                        marketplace=marketplace,
                        strategy_type=strategy_type,
                        strategy_adjustment_type=StrategyAdjustmentType.BID_THRESHOLD.value,
                        strategy_adjustment_reason="poor_prediction_accuracy",
                        extra_data={"accuracy_rate": accuracy.get("accuracy_rate")},
                    )
                    db.add(entry)
                    db.commit()

        except Exception as e:
            logger.error(f"Failed to check strategy adjustment: {e}")
            db.rollback()
        finally:
            db.close()

    def _maybe_trigger_weekly_review(self) -> None:
        """Trigger weekly review if enough time has passed."""
        now = datetime.utcnow()

        # Check if 7 days have passed since last review
        if (
            self._last_weekly_review is None
            or (now - self._last_weekly_review).days >= 7
        ):
            logger.info("Triggering weekly review")
            self.perform_weekly_review()

    def get_learning_history(
        self,
        limit: int = 100,
        event_type: LearningEventType | None = None,
        marketplace: str | None = None,
    ) -> list[LearningEntry]:
        """
        Get learning history.

        Args:
            limit: Maximum entries to return
            event_type: Filter by event type
            marketplace: Filter by marketplace

        Returns:
            List of learning entries
        """
        db = SessionLocal()
        try:
            query = db.query(LearningEntry)

            if event_type:
                query = query.filter(LearningEntry.event_type == event_type.value)
            if marketplace:
                query = query.filter(LearningEntry.marketplace == marketplace)

            query = query.order_by(LearningEntry.created_at.desc()).limit(limit)

            return query.all()

        finally:
            db.close()


# Global singleton instance
_learning_system_instance: ClosedLoopLearningSystem | None = None


def get_learning_system() -> ClosedLoopLearningSystem:
    """Get or create global learning system singleton."""
    global _learning_system_instance

    if _learning_system_instance is None:
        _learning_system_instance = ClosedLoopLearningSystem()

    return _learning_system_instance


def reset_learning_system():
    """Reset learning system singleton (useful for testing)."""
    global _learning_system_instance
    _learning_system_instance = None
