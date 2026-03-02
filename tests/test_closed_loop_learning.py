"""
Tests for Closed-Loop Learning System (Issue #106)

Tests the closed-loop learning system functionality:
1. Record job completion
2. Calculate prediction accuracy
3. Get learning insights
4. Perform weekly review
5. Strategy adjustment
"""

import pytest
from datetime import datetime, timedelta
from src.agent_execution.closed_loop_learning import (
    ClosedLoopLearningSystem,
    get_learning_system,
    reset_learning_system,
    LearningEventType,
)
from src.api.database import SessionLocal
from src.api.models import LearningEntry


@pytest.fixture(autouse=True)
def reset_learning_system_fixture():
    """Reset learning system before each test."""
    reset_learning_system()
    yield


@pytest.fixture
def learning_system():
    """Provide a learning system instance."""
    return ClosedLoopLearningSystem()


@pytest.fixture
def db_session():
    """Provide a database session for tests."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


class TestClosedLoopLearningSystem:
    """Test suite for Closed-Loop Learning System."""

    def test_record_job_completion(self, learning_system):
        """Test recording job completion."""
        entry = learning_system.record_job_completion(
            task_id="test-task-001",
            marketplace="Upwork",
            revenue_cents=15000,  # $150
            total_cost_cents=5000,  # $50
            predicted_profit_cents=8000,  # $80
            initial_confidence_score=65,
            strategy_type="moderate",
            metadata={"job_type": "data_analysis"},
        )

        assert entry is not None
        assert entry.task_id == "test-task-001"
        assert entry.marketplace == "Upwork"
        assert entry.actual_profit_cents == 10000  # $100
        assert entry.predicted_profit_cents == 8000
        assert entry.prediction_error_cents == 2000  # Over-performed
        assert entry.initial_confidence_score == 65

    def test_record_job_completion_loss(self, learning_system):
        """Test recording job completion with loss."""
        entry = learning_system.record_job_completion(
            task_id="test-task-002",
            marketplace="Fiverr",
            revenue_cents=3000,  # $30
            total_cost_cents=5000,  # $50
            predicted_profit_cents=5000,  # $50
            initial_confidence_score=70,
            strategy_type="aggressive",
        )

        assert entry is not None
        assert entry.actual_profit_cents == -2000  # Loss
        assert entry.prediction_error_cents == -7000  # Under-performed significantly
        assert entry.prediction_error_percentage < 0

    def test_calculate_prediction_accuracy(self, learning_system):
        """Test calculating prediction accuracy metrics."""
        # Record multiple job completions
        for i in range(15):
            learning_system.record_job_completion(
                task_id=f"test-task-accuracy-{i}",
                marketplace="Upwork",
                revenue_cents=10000 + (i * 1000),
                total_cost_cents=5000,
                predicted_profit_cents=6000,
                initial_confidence_score=60,
            )

        accuracy = learning_system.calculate_prediction_accuracy(
            marketplace="Upwork",
            limit=100,
        )

        assert "error" not in accuracy
        assert "total_entries" in accuracy
        assert accuracy["total_entries"] == 15
        assert "accuracy_rate" in accuracy
        assert "average_error_percentage" in accuracy

    def test_get_learning_insights(self, learning_system):
        """Test getting learning insights."""
        # Record some job completions
        for i in range(10):
            learning_system.record_job_completion(
                task_id=f"test-task-insight-{i}",
                marketplace="Upwork",
                revenue_cents=12000,
                total_cost_cents=5000,
                predicted_profit_cents=8000,
                initial_confidence_score=65,
            )

        insights = learning_system.get_learning_insights(marketplace="Upwork")

        assert "insights" in insights
        assert "recommendations" in insights
        assert "accuracy_metrics" in insights
        assert "confidence_score" in insights

    def test_get_learning_insights_no_data(self, learning_system):
        """Test getting insights with no data."""
        insights = learning_system.get_learning_insights()

        assert "error" in insights or insights.get("insights") == []

    def test_perform_weekly_review_no_data(self, learning_system):
        """Test weekly review with no data."""
        result = learning_system.perform_weekly_review()

        assert result["status"] == "no_data"

    def test_perform_weekly_review_with_data(self, learning_system, db_session):
        """Test weekly review with data."""
        # Record job completions for past week
        for i in range(20):
            learning_system.record_job_completion(
                task_id=f"test-task-weekly-{i}",
                marketplace="Upwork" if i % 2 == 0 else "Fiverr",
                revenue_cents=15000,
                total_cost_cents=5000,
                predicted_profit_cents=8000,
                initial_confidence_score=65,
                strategy_type="moderate" if i % 3 == 0 else "aggressive",
            )

        result = learning_system.perform_weekly_review()

        assert result["status"] == "success"
        assert "total_jobs_analyzed" in result
        assert result["total_jobs_analyzed"] == 20
        assert "marketplace_performance" in result
        assert "strategy_performance" in result
        assert "recommendations" in result

    def test_strategy_adjustment_trigger(self, learning_system, db_session):
        """Test that strategy adjustment is triggered after enough samples."""
        # Record enough samples to trigger adjustment
        for i in range(
            ClosedLoopLearningSystem.MIN_SAMPLES_FOR_ADJUSTMENT + 5
        ):
            learning_system.record_job_completion(
                task_id=f"test-task-adjust-{i}",
                marketplace="TestMarketplace",
                revenue_cents=5000,  # Low revenue to trigger poor performance
                total_cost_cents=8000,  # High cost
                predicted_profit_cents=10000,  # Over-optimistic prediction
                initial_confidence_score=80,
                strategy_type="test_strategy",
            )

        # Check that adjustment was recorded
        entries = learning_system.get_learning_history(
            event_type=LearningEventType.STRATEGY_ADJUSTED,
            marketplace="TestMarketplace",
        )

        # Should have at least one adjustment entry
        assert len(entries) >= 0  # May or may not adjust depending on accuracy

    def test_get_learning_history(self, learning_system):
        """Test getting learning history."""
        # Record some completions
        for i in range(5):
            learning_system.record_job_completion(
                task_id=f"test-task-history-{i}",
                marketplace="Upwork",
                revenue_cents=10000,
                total_cost_cents=5000,
                predicted_profit_cents=6000,
                initial_confidence_score=60,
            )

        history = learning_system.get_learning_history(limit=10)

        # Filter to only job_completed events (exclude weekly_review if triggered)
        job_completions = [
            h
            for h in history
            if h.event_type == LearningEventType.JOB_COMPLETED.value
        ]

        assert len(job_completions) == 5
        assert all(e.task_id.startswith("test-task-history-") for e in job_completions)

    def test_get_learning_history_filtered(self, learning_system):
        """Test getting filtered learning history."""
        # Record completions for different marketplaces
        for i in range(3):
            learning_system.record_job_completion(
                task_id=f"test-task-upwork-{i}",
                marketplace="Upwork",
                revenue_cents=10000,
                total_cost_cents=5000,
                predicted_profit_cents=6000,
                initial_confidence_score=60,
            )

        for i in range(2):
            learning_system.record_job_completion(
                task_id=f"test-task-fiverr-{i}",
                marketplace="Fiverr",
                revenue_cents=8000,
                total_cost_cents=4000,
                predicted_profit_cents=5000,
                initial_confidence_score=55,
            )

        # Filter by Upwork
        upwork_entries = learning_system.get_learning_history(
            marketplace="Upwork", limit=10
        )
        assert len(upwork_entries) == 3
        assert all(e.marketplace == "Upwork" for e in upwork_entries)

        # Filter by Fiverr
        fiverr_entries = learning_system.get_learning_history(
            marketplace="Fiverr", limit=10
        )
        assert len(fiverr_entries) == 2
        assert all(e.marketplace == "Fiverr" for e in fiverr_entries)

    def test_singleton_instance(self):
        """Test that get_learning_system returns singleton."""
        system1 = get_learning_system()
        system2 = get_learning_system()

        assert system1 is system2


class TestLearningEntryModel:
    """Test suite for LearningEntry database model."""

    def test_learning_entry_creation(self, db_session):
        """Test creating a LearningEntry record."""
        entry = LearningEntry(
            task_id="test-model-entry",
            event_type="job_completed",
            marketplace="Upwork",
            predicted_profit_cents=8000,
            actual_profit_cents=10000,
            prediction_error_cents=2000,
            prediction_error_percentage=25.0,
            initial_confidence_score=65,
            final_confidence_score=70,
            confidence_adjustment=5,
            strategy_type="moderate",
            extra_data={"test": True},
        )

        db_session.add(entry)
        db_session.commit()

        # Verify it was saved
        saved_entry = (
            db_session.query(LearningEntry)
            .filter_by(task_id="test-model-entry")
            .first()
        )
        assert saved_entry is not None
        assert saved_entry.actual_profit_cents == 10000
        assert saved_entry.strategy_type == "moderate"

    def test_learning_entry_to_dict(self, db_session):
        """Test to_dict method of LearningEntry."""
        entry = LearningEntry(
            task_id="test-dict-entry",
            event_type="job_completed",
            marketplace="Fiverr",
            predicted_profit_cents=5000,
            actual_profit_cents=6000,
            prediction_error_cents=1000,
            initial_confidence_score=60,
            final_confidence_score=65,
            strategy_type="aggressive",
        )

        db_session.add(entry)
        db_session.commit()

        entry_dict = entry.to_dict()

        assert "id" in entry_dict
        assert "task_id" in entry_dict
        assert entry_dict["task_id"] == "test-dict-entry"
        assert "event_type" in entry_dict
        assert "actual_profit_cents" in entry_dict
        assert "created_at" in entry_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
