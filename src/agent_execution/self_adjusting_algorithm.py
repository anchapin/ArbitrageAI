"""Self-Adjusting Confidence Algorithm.

Implements adaptive confidence calculation that learns and improves over time
based on performance patterns.

Issue #97: Self-Adjusting Confidence Algorithm

Features:
- Automatic adjustment based on win/loss patterns
- Conservatism scaling based on performance
- Comprehensive logging for human review
- Human override capabilities
- Performance improvement tracking
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.api.database import SessionLocal
from src.api.models import ConfidenceAdjustment, ConfidenceEntry
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AdjustmentReason(Enum):
    """Reasons for confidence adjustment."""

    WIN_STREAK = "win_streak"
    LOSS_STREAK = "loss_streak"
    POOR_PERFORMANCE = "poor_performance"
    PROFIT_DECLINE = "profit_decline"
    PROFIT_INCREASE = "profit_increase"
    HIGH_VARIANCE = "high_variance"
    LOW_SAMPLE_SIZE = "low_sample_size"
    MARKETPLACE_CHANGE = "marketplace_change"
    STRATEGY_CHANGE = "strategy_change"
    MANUAL_OVERRIDE = "manual_override"


class ConservatismLevel(Enum):
    """Conservatism levels for bidding strategy."""

    VERY_AGGRESSIVE = 10  # Bid on almost everything
    AGGRESSIVE = 30  # Low threshold
    MODERATE = 50  # Balanced approach
    CONSERVATIVE = 70  # Higher threshold
    VERY_CONSERVATIVE = 90  # Only bid on high confidence


class SelfAdjustingConfidenceAlgorithm:
    """Self-Adjusting Confidence Algorithm.

    Automatically adjusts confidence calculation parameters based on
    performance patterns to optimize profitability.

    Features:
    - Tracks win/loss patterns and adjusts conservatism
    - Logs all adjustments for human review
    - Supports manual overrides
    - Measures improvement over time
    """

    # Adjustment thresholds
    WIN_STREAK_THRESHOLD = 5  # Adjust after 5 consecutive wins
    LOSS_STREAK_THRESHOLD = 3  # Adjust after 3 consecutive losses
    PROFIT_DECLINE_THRESHOLD = 0.2  # 20% decline triggers adjustment
    MIN_SAMPLES_FOR_ADJUSTMENT = 10  # Minimum entries before adjusting

    def __init__(self):
        """Initialize Self-Adjusting Confidence Algorithm."""
        self.current_conservatism = ConservatismLevel.MODERATE.value
        self.baseline_conservatism = ConservatismLevel.MODERATE.value
        self.total_adjustments = 0
        self.adjustment_history: list[dict[str, Any]] = []
        self.performance_baseline: dict[str, Any] | None = None
        self._load_state()

    def _load_state(self):
        """Load algorithm state from database."""
        db = SessionLocal()
        try:
            # Get the most recent adjustment to determine current state
            last_adjustment = (
                db.query(ConfidenceAdjustment)
                .order_by(ConfidenceAdjustment.created_at.desc())
                .first()
            )

            if last_adjustment:
                self.current_conservatism = last_adjustment.new_conservatism
                self.total_adjustments = last_adjustment.total_adjustments
                logger.info(
                    f"Loaded algorithm state - Conservatism: {self.current_conservatism}, "
                    f"Total adjustments: {self.total_adjustments}",
                )
            else:
                logger.info("Initialized new algorithm state with default conservatism")
        finally:
            db.close()

    def analyze_performance(self) -> dict[str, Any]:
        """Analyze recent performance to determine if adjustment is needed.

        Returns:
            Dictionary with performance analysis and recommendations
        """
        db = SessionLocal()
        try:
            # Get recent entries (last 50 bids)
            recent_entries = (
                db.query(ConfidenceEntry)
                .order_by(ConfidenceEntry.created_at.desc())
                .limit(50)
                .all()
            )

            if len(recent_entries) < self.MIN_SAMPLES_FOR_ADJUSTMENT:
                return {
                    "needs_adjustment": False,
                    "reason": f"Insufficient data: {len(recent_entries)} < {self.MIN_SAMPLES_FOR_ADJUSTMENT}",
                    "current_entries": len(recent_entries),
                }

            # Calculate recent performance metrics
            total = len(recent_entries)
            wins = sum(1 for e in recent_entries if e.won)
            losses = total - wins
            win_rate = wins / total if total > 0 else 0

            # Calculate profit metrics
            profitable_wins = [e for e in recent_entries if e.won and e.profit_cents]
            avg_profit = (
                sum(e.profit_cents for e in profitable_wins) / len(profitable_wins)
                if profitable_wins
                else 0
            )
            total_profit = sum(e.profit_cents for e in profitable_wins)

            # Calculate streak information
            current_win_streak = 0
            current_loss_streak = 0

            for entry in recent_entries:
                if entry.won:
                    current_win_streak += 1
                    if current_loss_streak > 0:
                        break
                else:
                    current_loss_streak += 1
                    if current_win_streak > 0:
                        break

            # Calculate variance
            variance = SelfAdjustingConfidenceAlgorithm._calculate_profit_variance(profitable_wins)

            # Compare with baseline if available
            improvement = None
            if self.performance_baseline:
                baseline_win_rate = self.performance_baseline.get("win_rate", 0)
                baseline_profit = self.performance_baseline.get("avg_profit", 0)

                win_rate_change = win_rate - baseline_win_rate
                profit_change = (
                    (avg_profit - baseline_profit) / baseline_profit
                    if baseline_profit > 0
                    else 0
                )

                improvement = {
                    "win_rate_change": win_rate_change,
                    "profit_change": profit_change,
                    "is_improving": win_rate_change > 0 and profit_change > 0,
                }

            # Determine if adjustment is needed
            needs_adjustment = False
            adjustment_reason = None

            if current_win_streak >= self.WIN_STREAK_THRESHOLD:
                needs_adjustment = True
                adjustment_reason = AdjustmentReason.WIN_STREAK
            elif current_loss_streak >= self.LOSS_STREAK_THRESHOLD:
                needs_adjustment = True
                adjustment_reason = AdjustmentReason.LOSS_STREAK
            elif variance > 10000:  # High variance
                needs_adjustment = True
                adjustment_reason = AdjustmentReason.HIGH_VARIANCE

            return {
                "needs_adjustment": needs_adjustment,
                "adjustment_reason": adjustment_reason.value if adjustment_reason else None,
                "total_bids": total,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "avg_profit_cents": avg_profit,
                "total_profit_cents": total_profit,
                "current_win_streak": current_win_streak,
                "current_loss_streak": current_loss_streak,
                "variance": variance,
                "improvement": improvement,
                "recent_entries_count": len(recent_entries),
            }

        finally:
            db.close()

    @staticmethod
    def _calculate_profit_variance(profitable_wins: list[ConfidenceEntry]) -> float:
        """Calculate variance in profit outcomes."""
        if len(profitable_wins) < 2:
            return 0

        profits = [e.profit_cents for e in profitable_wins]
        mean = sum(profits) / len(profits)
        return sum((p - mean) ** 2 for p in profits) / len(profits)

    def adjust_conservatism(
        self,
        reason: AdjustmentReason,
        manual_override: bool = False,
        override_value: int | None = None,
    ) -> dict[str, Any]:
        """Adjust conservatism level based on performance or manual override.

        Args:
            reason: Reason for adjustment
            manual_override: Whether this is a manual override
            override_value: Optional specific value to set

        Returns:
            Dictionary with adjustment details
        """
        db = SessionLocal()
        try:
            old_conservatism = self.current_conservatism

            if manual_override and override_value is not None:
                # Manual override
                self.current_conservatism = override_value
                reason = AdjustmentReason.MANUAL_OVERRIDE
                logger.info(
                    f"Manual override: Conservatism {old_conservatism} -> {override_value}",
                )
            # Automatic adjustment based on reason
            elif reason == AdjustmentReason.WIN_STREAK:
                # Reduce conservatism (more aggressive)
                adjustment = -10
                self.current_conservatism = max(
                    ConservatismLevel.VERY_AGGRESSIVE.value,
                    self.current_conservatism + adjustment,
                )
                logger.info(
                    f"Win streak detected: Reducing conservatism to {self.current_conservatism}",
                )

            elif reason == AdjustmentReason.LOSS_STREAK:
                # Increase conservatism (more cautious)
                adjustment = +15
                self.current_conservatism = min(
                    ConservatismLevel.VERY_CONSERVATIVE.value,
                    self.current_conservatism + adjustment,
                )
                logger.info(
                    f"Loss streak detected: Increasing conservatism to {self.current_conservatism}",
                )

            elif reason == AdjustmentReason.HIGH_VARIANCE:
                # Increase conservatism due to unpredictability
                adjustment = +10
                self.current_conservatism = min(
                    ConservatismLevel.VERY_CONSERVATIVE.value,
                    self.current_conservatism + adjustment,
                )
                logger.info(
                    f"High variance detected: Increasing conservatism to {self.current_conservatism}",
                )

            elif reason == AdjustmentReason.PROFIT_INCREASE:
                # Slightly reduce conservatism (success)
                adjustment = -5
                self.current_conservatism = max(
                    ConservatismLevel.VERY_AGGRESSIVE.value,
                    self.current_conservatism + adjustment,
                )
                logger.info(
                    f"Profit increase: Slightly reducing conservatism to {self.current_conservatism}",
                )

            elif reason == AdjustmentReason.PROFIT_DECLINE:
                # Increase conservatism (underperforming)
                adjustment = +10
                self.current_conservatism = min(
                    ConservatismLevel.VERY_CONSERVATIVE.value,
                    self.current_conservatism + adjustment,
                )
                logger.info(
                    f"Profit decline: Increasing conservatism to {self.current_conservatism}",
                )

            # Increment total adjustments
            self.total_adjustments += 1

            # Create adjustment record
            adjustment_record = ConfidenceAdjustment(
                id=str(hash(f"{datetime.now(timezone.utc).isoformat()}{self.total_adjustments}")),
                old_conservatism=old_conservatism,
                new_conservatism=self.current_conservatism,
                adjustment_reason=reason.value,
                total_adjustments=self.total_adjustments,
                is_manual_override=manual_override,
                created_at=datetime.now(timezone.utc),
            )

            db.add(adjustment_record)
            db.commit()

            # Store in history
            adjustment_info = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "old_conservatism": old_conservatism,
                "new_conservatism": self.current_conservatism,
                "reason": reason.value,
                "is_manual_override": manual_override,
                "total_adjustments": self.total_adjustments,
            }
            self.adjustment_history.append(adjustment_info)

            # Update performance baseline
            self._update_performance_baseline(db)

            logger.info(
                f"Conservatism adjusted: {old_conservatism} -> {self.current_conservatism} "
                f"({reason.value})",
            )

            return {
                "success": True,
                "old_conservatism": old_conservatism,
                "new_conservatism": self.current_conservatism,
                "reason": reason.value,
                "is_manual_override": manual_override,
                "total_adjustments": self.total_adjustments,
                "timestamp": adjustment_info["timestamp"],
            }

        except Exception as e:
            logger.error(f"Failed to adjust conservatism: {e}")
            db.rollback()
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            db.close()

    def _update_performance_baseline(self, db: SessionLocal):
        """Update performance baseline for future comparisons."""
        recent_entries = (
            db.query(ConfidenceEntry)
            .order_by(ConfidenceEntry.created_at.desc())
            .limit(50)
            .all()
        )

        if len(recent_entries) < self.MIN_SAMPLES_FOR_ADJUSTMENT:
            return

        wins = sum(1 for e in recent_entries if e.won)
        profitable_wins = [e for e in recent_entries if e.won and e.profit_cents]
        avg_profit = (
            sum(e.profit_cents for e in profitable_wins) / len(profitable_wins)
            if profitable_wins
            else 0
        )

        self.performance_baseline = {
            "win_rate": wins / len(recent_entries),
            "avg_profit": avg_profit,
            "total_bids": len(recent_entries),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_adjusted_threshold(self, base_threshold: int) -> int:
        """Get adjusted threshold based on current conservatism.

        Args:
            base_threshold: Base threshold from confidence calculation

        Returns:
            Adjusted threshold
        """
        # Blend base threshold with conservatism level
        # Higher conservatism = higher threshold required
        adjustment_factor = (self.current_conservatism - 50) / 100  # -0.4 to +0.4
        adjusted = base_threshold * (1 + adjustment_factor)

        return int(max(0, min(100, adjusted)))

    def get_algorithm_status(self) -> dict[str, Any]:
        """Get current algorithm status and configuration.

        Returns:
            Dictionary with algorithm state and metrics
        """
        db = SessionLocal()
        try:
            # Get recent performance
            performance = self.analyze_performance()

            # Get adjustment history (last 10)
            recent_adjustments = (
                db.query(ConfidenceAdjustment)
                .order_by(ConfidenceAdjustment.created_at.desc())
                .limit(10)
                .all()
            )

            # Calculate improvement metrics
            improvement_metrics = self._calculate_improvement_metrics(db)

            # Get conservatism level name
            conservatism_name = None
            for level in ConservatismLevel:
                if level.value == self.current_conservatism:
                    conservatism_name = level.name
                    break

            if not conservatism_name:
                # Find closest level
                closest = min(
                    ConservatismLevel,
                    key=lambda x: abs(x.value - self.current_conservatism),
                )
                conservatism_name = f"{closest.name} ({self.current_conservatism})"

            return {
                "current_conservatism": self.current_conservatism,
                "conservatism_level": conservatism_name,
                "baseline_conservatism": self.baseline_conservatism,
                "total_adjustments": self.total_adjustments,
                "performance": performance,
                "performance_baseline": self.performance_baseline,
                "improvement_metrics": improvement_metrics,
                "recent_adjustments": [
                    {
                        "timestamp": adj.created_at.isoformat() if adj.created_at else None,
                        "old_conservatism": adj.old_conservatism,
                        "new_conservatism": adj.new_conservatism,
                        "reason": adj.adjustment_reason,
                        "is_manual_override": adj.is_manual_override,
                    }
                    for adj in recent_adjustments
                ],
            }

        finally:
            db.close()

    def _calculate_improvement_metrics(self, db: SessionLocal) -> dict[str, Any]:
        """Calculate improvement metrics over time."""
        # Get all adjustments
        adjustments = (
            db.query(ConfidenceAdjustment)
            .order_by(ConfidenceAdjustment.created_at.asc())
            .all()
        )

        if len(adjustments) < 2:
            return {
                "total_adjustments": len(adjustments),
                "message": "Insufficient data for improvement metrics",
            }

        # Compare first and last performance
        first_adjustment = adjustments[0]

        # Get performance at start and now
        start_time = first_adjustment.created_at

        # Make start_time timezone-aware if it's naive
        if start_time and start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        # This would ideally query performance at those time periods
        # For now, use baseline if available
        if self.performance_baseline:
            return {
                "total_adjustments": len(adjustments),
                "current_win_rate": self.performance_baseline.get("win_rate", 0),
                "current_avg_profit": self.performance_baseline.get("avg_profit", 0),
                "algorithm_age_days": (datetime.now(timezone.utc) - start_time).days if start_time else 0,
                "adjustments_per_day": len(adjustments)
                / max((datetime.now(timezone.utc) - start_time).days, 1)
                if start_time
                else 0,
            }

        return {
            "total_adjustments": len(adjustments),
            "message": "No baseline performance data available",
        }

    def manual_override(
        self,
        conservatism_value: int,
        reason: str = "Manual adjustment by user",
    ) -> dict[str, Any]:
        """Manually override conservatism level.

        Args:
            conservatism_value: New conservatism value (0-100)
            reason: Reason for manual override

        Returns:
            Dictionary with override result
        """
        if not 0 <= conservatism_value <= 100:
            return {
                "success": False,
                "error": "Conservatism value must be between 0 and 100",
            }

        result = self.adjust_conservatism(
            reason=AdjustmentReason.MANUAL_OVERRIDE,
            manual_override=True,
            override_value=conservatism_value,
        )

        if result["success"]:
            logger.info(f"Manual override successful: {reason}")
            result["user_reason"] = reason

        return result

    def reset_to_baseline(self) -> dict[str, Any]:
        """Reset conservatism to baseline value.

        Returns:
            Dictionary with reset result
        """
        old_value = self.current_conservatism
        self.current_conservatism = self.baseline_conservatism

        logger.info(
            f"Reset to baseline: {old_value} -> {self.baseline_conservatism}",
        )

        return {
            "success": True,
            "old_conservatism": old_value,
            "new_conservatism": self.baseline_conservatism,
            "message": "Conservatism reset to baseline",
        }


# Global singleton instance
_algorithm_instance: SelfAdjustingConfidenceAlgorithm | None = None


def get_self_adjusting_algorithm() -> SelfAdjustingConfidenceAlgorithm:
    """Get or create global Self-Adjusting Algorithm singleton."""
    global _algorithm_instance  # noqa: PLW0603

    if _algorithm_instance is None:
        _algorithm_instance = SelfAdjustingConfidenceAlgorithm()

    return _algorithm_instance


def reset_self_adjusting_algorithm():
    """Reset algorithm singleton and clear database state (useful for testing)."""
    global _algorithm_instance  # noqa: PLW0603
    _algorithm_instance = None
    # Also clear algorithm state in database for fresh test runs
    db = SessionLocal()
    try:
        db.query(ConfidenceAdjustment).delete()
        db.query(ConfidenceEntry).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
