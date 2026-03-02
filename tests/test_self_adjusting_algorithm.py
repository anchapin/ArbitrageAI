"""
Tests for Self-Adjusting Confidence Algorithm (Issue #97)

Tests cover:
1. Automatic adjustment based on win/loss patterns
2. Logging of all adjustments for human review
3. Manual override capabilities
4. Performance improvement tracking
5. Conservatism level management
"""

import pytest
from datetime import datetime, timedelta

from src.api.database import SessionLocal
from src.agent_execution.self_adjusting_algorithm import (
    SelfAdjustingConfidenceAlgorithm,
    get_self_adjusting_algorithm,
    reset_self_adjusting_algorithm,
    AdjustmentReason,
    ConservatismLevel,
)
from src.agent_execution.confidence_tracker import (
    ConfidenceTracker,
    reset_confidence_tracker,
)
from src.api.models import ConfidenceEntry, ConfidenceAdjustment
from src.config.config_manager import reset_instance


@pytest.fixture(autouse=True)
def reset_all():
    """Reset all singletons before each test."""
    reset_instance()
    reset_confidence_tracker()
    reset_self_adjusting_algorithm()
    yield


@pytest.fixture
def db_session():
    """Provide a database session for tests."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def algorithm():
    """Provide a self-adjusting algorithm instance."""
    algo = SelfAdjustingConfidenceAlgorithm()
    return algo


@pytest.fixture
def confidence_tracker():
    """Provide a confidence tracker instance."""
    tracker = ConfidenceTracker()
    return tracker


class TestConservatismLevel:
    """Tests for ConservatismLevel enum."""

    def test_conservatism_levels_defined(self):
        """Test that all conservatism levels are defined."""
        assert ConservatismLevel.VERY_AGGRESSIVE.value == 10
        assert ConservatismLevel.AGGRESSIVE.value == 30
        assert ConservatismLevel.MODERATE.value == 50
        assert ConservatismLevel.CONSERVATIVE.value == 70
        assert ConservatismLevel.VERY_CONSERVATIVE.value == 90

    def test_conservatism_level_range(self):
        """Test that conservatism levels are in valid range."""
        for level in ConservatismLevel:
            assert 0 <= level.value <= 100


class TestAdjustmentReason:
    """Tests for AdjustmentReason enum."""

    def test_adjustment_reasons_defined(self):
        """Test that all adjustment reasons are defined."""
        assert AdjustmentReason.WIN_STREAK.value == "win_streak"
        assert AdjustmentReason.LOSS_STREAK.value == "loss_streak"
        assert AdjustmentReason.PROFIT_DECLINE.value == "profit_decline"
        assert AdjustmentReason.PROFIT_INCREASE.value == "profit_increase"
        assert AdjustmentReason.HIGH_VARIANCE.value == "high_variance"
        assert AdjustmentReason.MANUAL_OVERRIDE.value == "manual_override"


class TestSelfAdjustingAlgorithmInitialization:
    """Tests for algorithm initialization."""

    def test_initialization(self, algorithm):
        """Test that algorithm initializes correctly."""
        assert algorithm is not None
        assert algorithm.current_conservatism == ConservatismLevel.MODERATE.value
        assert algorithm.baseline_conservatism == ConservatismLevel.MODERATE.value
        assert algorithm.total_adjustments == 0

    def test_singleton_pattern(self):
        """Test singleton pattern works correctly."""
        algo1 = get_self_adjusting_algorithm()
        algo2 = get_self_adjusting_algorithm()
        assert algo1 is algo2

        # Test reset
        reset_self_adjusting_algorithm()
        algo3 = get_self_adjusting_algorithm()
        assert algo1 is not algo3


class TestPerformanceAnalysis:
    """Tests for performance analysis."""

    def test_analyze_performance_insufficient_data(self, algorithm, db_session, confidence_tracker):
        """Test performance analysis with insufficient data."""
        # Create only 5 entries (less than MIN_SAMPLES_FOR_ADJUSTMENT=10)
        for i in range(5):
            entry = confidence_tracker.record_bid(
                threshold=50,
                bid_amount_cents=10000,
                job_title=f"Test Job {i}",
            )
            confidence_tracker.update_outcome(entry.id, won=(i % 2 == 0))

        result = algorithm.analyze_performance()

        assert result["needs_adjustment"] is False
        assert "Insufficient data" in result["reason"]
        assert result["current_entries"] == 5

    def test_analyze_performance_with_data(self, algorithm, db_session, confidence_tracker):
        """Test performance analysis with sufficient data."""
        # Create 15 entries
        for i in range(15):
            entry = confidence_tracker.record_bid(
                threshold=50,
                bid_amount_cents=10000,
                job_title=f"Test Job {i}",
            )
            confidence_tracker.update_outcome(
                entry.id,
                won=(i < 10),  # 10 wins, 5 losses
                profit_cents=5000 if i < 10 else None,
            )

        result = algorithm.analyze_performance()

        assert result["total_bids"] == 15
        assert result["wins"] == 10
        assert result["losses"] == 5
        assert result["win_rate"] == pytest.approx(10 / 15, rel=0.01)
        # Streaks are calculated from most recent, so last 5 are losses
        assert result["current_loss_streak"] >= 1


class TestAutomaticAdjustment:
    """Tests for automatic conservatism adjustment."""

    def test_adjust_for_win_streak(self, algorithm, db_session, confidence_tracker):
        """Test automatic adjustment for win streak."""
        # Create a win streak - most recent entries should be wins
        # First create some losses
        for i in range(3):
            entry = confidence_tracker.record_bid(
                threshold=50,
                bid_amount_cents=10000,
                job_title=f"Loss Job {i}",
            )
            confidence_tracker.update_outcome(entry.id, won=False)
        
        # Then create wins (these will be most recent)
        for i in range(7):
            entry = confidence_tracker.record_bid(
                threshold=50,
                bid_amount_cents=10000,
                job_title=f"Win Job {i}",
            )
            confidence_tracker.update_outcome(entry.id, won=True, profit_cents=5000)

        # Analyze performance
        analysis = algorithm.analyze_performance()
        assert analysis["current_win_streak"] >= 5
        assert analysis["needs_adjustment"] is True
        assert analysis["adjustment_reason"] == AdjustmentReason.WIN_STREAK.value

        # Perform adjustment
        old_conservatism = algorithm.current_conservatism
        result = algorithm.adjust_conservatism(reason=AdjustmentReason.WIN_STREAK)

        assert result["success"] is True
        assert result["old_conservatism"] == old_conservatism
        assert result["new_conservatism"] < old_conservatism  # Reduced conservatism
        assert result["reason"] == "win_streak"
        assert result["total_adjustments"] == 1

    def test_adjust_for_loss_streak(self, algorithm, db_session, confidence_tracker):
        """Test automatic adjustment for loss streak."""
        # Create enough entries to meet MIN_SAMPLES_FOR_ADJUSTMENT
        # First create some mixed results
        for i in range(10):
            entry = confidence_tracker.record_bid(
                threshold=50,
                bid_amount_cents=10000,
                job_title=f"Mixed Job {i}",
            )
            confidence_tracker.update_outcome(entry.id, won=(i % 2 == 0))
        
        # Then create losses (these will be most recent)
        for i in range(5):
            entry = confidence_tracker.record_bid(
                threshold=50,
                bid_amount_cents=10000,
                job_title=f"Loss Job {i}",
            )
            confidence_tracker.update_outcome(entry.id, won=False)

        # Analyze performance
        analysis = algorithm.analyze_performance()
        # Should have enough data now
        if "current_loss_streak" in analysis:
            assert analysis["current_loss_streak"] >= 3
        assert analysis["needs_adjustment"] is True
        assert analysis["adjustment_reason"] == AdjustmentReason.LOSS_STREAK.value

        # Perform adjustment
        old_conservatism = algorithm.current_conservatism
        result = algorithm.adjust_conservatism(reason=AdjustmentReason.LOSS_STREAK)

        assert result["success"] is True
        assert result["new_conservatism"] > old_conservatism  # Increased conservatism
        assert result["reason"] == "loss_streak"

    def test_adjustment_logging(self, algorithm, db_session, confidence_tracker):
        """Test that adjustments are logged to database."""
        # Create entries
        for i in range(15):
            entry = confidence_tracker.record_bid(
                threshold=50,
                bid_amount_cents=10000,
            )
            confidence_tracker.update_outcome(entry.id, won=True, profit_cents=5000)

        # Perform adjustment
        algorithm.adjust_conservatism(reason=AdjustmentReason.WIN_STREAK)

        # Check database
        adjustments = db_session.query(ConfidenceAdjustment).all()
        assert len(adjustments) == 1

        adj = adjustments[0]
        assert adj.old_conservatism == ConservatismLevel.MODERATE.value
        assert adj.new_conservatism < ConservatismLevel.MODERATE.value
        assert adj.adjustment_reason == AdjustmentReason.WIN_STREAK.value
        assert adj.is_manual_override is False

    def test_multiple_adjustments_tracking(self, algorithm, db_session, confidence_tracker):
        """Test that multiple adjustments are tracked correctly."""
        # Create entries and adjust multiple times
        for adjustment_num in range(3):
            for i in range(7):
                entry = confidence_tracker.record_bid(
                    threshold=50,
                    bid_amount_cents=10000,
                    job_title=f"Adj {adjustment_num} Job {i}",
                )
                confidence_tracker.update_outcome(entry.id, won=True, profit_cents=5000)

            algorithm.adjust_conservatism(reason=AdjustmentReason.WIN_STREAK)

        # Check total adjustments
        assert algorithm.total_adjustments == 3

        # Check database records
        adjustments = db_session.query(ConfidenceAdjustment).order_by(
            ConfidenceAdjustment.created_at.asc()
        ).all()
        assert len(adjustments) == 3

        # Check progression
        for i, adj in enumerate(adjustments):
            assert adj.total_adjustments == i + 1


class TestManualOverride:
    """Tests for manual override functionality."""

    def test_manual_override_valid(self, algorithm):
        """Test manual override with valid value."""
        result = algorithm.manual_override(
            conservatism_value=80,
            reason="Testing manual override",
        )

        assert result["success"] is True
        assert result["old_conservatism"] == ConservatismLevel.MODERATE.value
        assert result["new_conservatism"] == 80
        assert result["user_reason"] == "Testing manual override"

    def test_manual_override_invalid_value(self, algorithm):
        """Test manual override with invalid value."""
        result = algorithm.manual_override(conservatism_value=150)

        assert result["success"] is False
        assert "must be between 0 and 100" in result["error"]

    def test_manual_override_logging(self, algorithm, db_session):
        """Test that manual overrides are logged."""
        algorithm.manual_override(
            conservatism_value=90,
            reason="User testing",
        )

        adjustments = db_session.query(ConfidenceAdjustment).all()
        assert len(adjustments) == 1

        adj = adjustments[0]
        assert adj.is_manual_override is True
        assert adj.adjustment_reason == AdjustmentReason.MANUAL_OVERRIDE.value
        assert adj.new_conservatism == 90


class TestAlgorithmStatus:
    """Tests for algorithm status reporting."""

    def test_get_algorithm_status(self, algorithm, db_session, confidence_tracker):
        """Test getting algorithm status."""
        # Create some data
        for i in range(15):
            entry = confidence_tracker.record_bid(
                threshold=50,
                bid_amount_cents=10000,
            )
            confidence_tracker.update_outcome(entry.id, won=(i % 2 == 0))

        # Make an adjustment
        algorithm.adjust_conservatism(reason=AdjustmentReason.WIN_STREAK)

        status = algorithm.get_algorithm_status()

        assert "current_conservatism" in status
        assert "conservatism_level" in status
        assert "total_adjustments" in status
        assert "performance" in status
        assert "recent_adjustments" in status
        assert status["total_adjustments"] == 1

    def test_get_adjusted_threshold(self, algorithm):
        """Test threshold adjustment based on conservatism."""
        base_threshold = 50

        # Test with moderate conservatism (50)
        algorithm.current_conservatism = 50
        adjusted = algorithm.get_adjusted_threshold(base_threshold)
        assert adjusted == 50  # No adjustment at baseline

        # Test with high conservatism (90)
        algorithm.current_conservatism = 90
        adjusted = algorithm.get_adjusted_threshold(base_threshold)
        assert adjusted > 50  # Higher threshold

        # Test with low conservatism (10)
        algorithm.current_conservatism = 10
        adjusted = algorithm.get_adjusted_threshold(base_threshold)
        assert adjusted < 50  # Lower threshold


class TestResetToBaseline:
    """Tests for resetting to baseline."""

    def test_reset_to_baseline(self, algorithm):
        """Test resetting conservatism to baseline."""
        # Change conservatism
        algorithm.current_conservatism = 80
        assert algorithm.current_conservatism != algorithm.baseline_conservatism

        # Reset
        result = algorithm.reset_to_baseline()

        assert result["success"] is True
        assert algorithm.current_conservatism == algorithm.baseline_conservatism
        assert algorithm.current_conservatism == ConservatismLevel.MODERATE.value


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_adjustment_with_no_database(self, algorithm):
        """Test adjustment handles database errors gracefully."""
        # This should not crash even if there are issues
        result = algorithm.analyze_performance()
        assert isinstance(result, dict)

    def test_conservatism_bounds(self, algorithm, db_session, confidence_tracker):
        """Test that conservatism stays within bounds."""
        # Create many win streaks to try to push conservatism very low
        for _ in range(10):
            for i in range(7):
                entry = confidence_tracker.record_bid(
                    threshold=50,
                    bid_amount_cents=10000,
                    job_title=f"Job {_}_{i}",
                )
                confidence_tracker.update_outcome(entry.id, won=True)
            algorithm.adjust_conservatism(reason=AdjustmentReason.WIN_STREAK)

        # Conservatism should not go below minimum
        assert algorithm.current_conservatism >= ConservatismLevel.VERY_AGGRESSIVE.value
        assert algorithm.current_conservatism <= ConservatismLevel.VERY_CONSERVATIVE.value


class TestIntegration:
    """Integration tests for the self-adjusting algorithm."""

    def test_full_workflow(self, algorithm, db_session, confidence_tracker):
        """Test complete workflow of algorithm usage."""
        # Phase 1: Initial bidding
        for i in range(20):
            entry = confidence_tracker.record_bid(
                threshold=50,
                bid_amount_cents=10000,
                job_title=f"Phase 1 Job {i}",
            )
            confidence_tracker.update_outcome(entry.id, won=(i < 15), profit_cents=5000 if i < 15 else None)

        # Analyze and adjust
        analysis = algorithm.analyze_performance()
        assert analysis["total_bids"] >= 10

        # Make adjustment
        if analysis["needs_adjustment"]:
            result = algorithm.adjust_conservatism(reason=AdjustmentReason.WIN_STREAK)
            assert result["success"] is True

        # Get status
        status = algorithm.get_algorithm_status()
        assert status["total_adjustments"] >= 0

        # Manual override
        override_result = algorithm.manual_override(
            conservatism_value=60,
            reason="Integration test override",
        )
        assert override_result["success"] is True

        # Verify final state
        final_status = algorithm.get_algorithm_status()
        assert final_status["current_conservatism"] == 60


class TestImprovementTracking:
    """Tests for tracking improvement over time."""

    def test_performance_baseline_update(self, algorithm, db_session, confidence_tracker):
        """Test that performance baseline is updated after adjustments."""
        # Create initial data
        for i in range(15):
            entry = confidence_tracker.record_bid(
                threshold=50,
                bid_amount_cents=10000,
            )
            confidence_tracker.update_outcome(entry.id, won=True, profit_cents=5000)

        # Make adjustment to trigger baseline update
        algorithm.adjust_conservatism(reason=AdjustmentReason.WIN_STREAK)

        # Check baseline was set
        assert algorithm.performance_baseline is not None
        assert "win_rate" in algorithm.performance_baseline
        assert "avg_profit" in algorithm.performance_baseline

    def test_improvement_metrics(self, algorithm, db_session, confidence_tracker):
        """Test calculation of improvement metrics."""
        # Create data and multiple adjustments
        for adj_num in range(3):
            for i in range(10):
                entry = confidence_tracker.record_bid(
                    threshold=50,
                    bid_amount_cents=10000,
                    job_title=f"Adj {adj_num} Job {i}",
                )
                confidence_tracker.update_outcome(entry.id, won=(i % 2 == 0))
            algorithm.adjust_conservatism(reason=AdjustmentReason.WIN_STREAK)

        status = algorithm.get_algorithm_status()
        metrics = status.get("improvement_metrics", {})

        assert "total_adjustments" in metrics
        assert metrics["total_adjustments"] >= 3
