"""
Tests for Auto-Execution Pipeline (Issue #104)
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.agent_execution.auto_execution import (
    AutoExecutionPipeline,
    ExecutionStrategy,
    ExecutionResult,
    BidDecision,
    get_auto_execution_pipeline,
    reset_auto_execution_pipeline,
)


class TestExecutionStrategy:
    """Test execution strategy enum."""

    def test_strategies_defined(self):
        """Test all strategies are defined."""
        assert ExecutionStrategy.AGGRESSIVE.value == "aggressive"
        assert ExecutionStrategy.CONSERVATIVE.value == "conservative"
        assert ExecutionStrategy.BALANCED.value == "balanced"
        assert ExecutionStrategy.LEARNING.value == "learning"


class TestExecutionResult:
    """Test execution result data structure."""

    def test_execution_result_success(self):
        """Test successful execution result."""
        result = ExecutionResult(
            success=True,
            task_id="task_123",
            bid_id="bid_456",
            bid_amount_cents=10000,
            confidence_score=0.85,
            execution_time_ms=1500.0,
            strategy_used="balanced",
        )
        
        assert result.success is True
        assert result.task_id == "task_123"
        assert result.error_message is None

    def test_execution_result_failure(self):
        """Test failed execution result."""
        result = ExecutionResult(
            success=False,
            task_id=None,
            bid_id=None,
            bid_amount_cents=0,
            confidence_score=0.0,
            execution_time_ms=100.0,
            strategy_used="balanced",
            error_message="Test error",
        )
        
        assert result.success is False
        assert result.error_message == "Test error"


class TestBidDecision:
    """Test bid decision data structure."""

    def test_bid_decision_should_bid(self):
        """Test bid decision to bid."""
        decision = BidDecision(
            should_bid=True,
            confidence=0.85,
            recommended_amount_cents=10000,
            reasoning="High confidence",
            risk_level="low",
        )
        
        assert decision.should_bid is True
        assert decision.confidence == 0.85
        assert decision.risk_level == "low"

    def test_bid_decision_should_not_bid(self):
        """Test bid decision not to bid."""
        decision = BidDecision(
            should_bid=False,
            confidence=0.45,
            recommended_amount_cents=0,
            reasoning="Low confidence",
            risk_level="high",
        )
        
        assert decision.should_bid is False
        assert decision.recommended_amount_cents == 0


class TestAutoExecutionPipeline:
    """Test auto-execution pipeline."""

    @pytest.fixture
    def pipeline(self):
        """Create auto-execution pipeline."""
        return AutoExecutionPipeline(
            strategy=ExecutionStrategy.BALANCED,
            min_confidence_threshold=0.6,
            max_bid_amount_cents=50000,
            retry_attempts=2,
            retry_delay_seconds=0.1,
        )

    def test_pipeline_initialization(self, pipeline):
        """Test pipeline initializes correctly."""
        assert pipeline.strategy == ExecutionStrategy.BALANCED
        assert pipeline.min_confidence_threshold == 0.6
        assert pipeline.max_bid_amount_cents == 50000
        assert pipeline.retry_attempts == 2

    @pytest.mark.asyncio
    async def test_analyze_opportunity_high_confidence(self, pipeline):
        """Test analyzing high confidence opportunity."""
        opportunity = {
            "title": "Test Task",
            "description": "Test Description",
            "budget_cents": 20000,
            "marketplace": "test",
            "domain": "general",
        }
        
        decision = await pipeline._analyze_opportunity(opportunity)
        
        assert isinstance(decision, BidDecision)
        assert decision.confidence >= 0.0
        assert decision.recommended_amount_cents >= 0

    @pytest.mark.asyncio
    async def test_analyze_opportunity_budget_calculation(self, pipeline):
        """Test budget calculation in analysis."""
        opportunity = {
            "title": "Test Task",
            "budget_cents": 10000,
            "marketplace": "test",
        }
        
        decision = await pipeline._analyze_opportunity(opportunity)
        
        # Bid amount should be within limits
        assert decision.recommended_amount_cents <= pipeline.max_bid_amount_cents
        assert decision.recommended_amount_cents >= 0

    def test_calculate_bid_amount_high_confidence(self, pipeline):
        """Test bid amount calculation for high confidence."""
        amount = pipeline._calculate_bid_amount(
            budget_cents=10000,
            confidence=0.85,
            strategy=ExecutionStrategy.BALANCED,
        )
        
        # Should bid 80% of budget for high confidence
        assert amount == 8000

    def test_calculate_bid_amount_medium_confidence(self, pipeline):
        """Test bid amount calculation for medium confidence."""
        amount = pipeline._calculate_bid_amount(
            budget_cents=10000,
            confidence=0.65,
            strategy=ExecutionStrategy.BALANCED,
        )
        
        # Should bid 60% of budget for medium confidence
        assert amount == 6000

    def test_calculate_bid_amount_low_confidence(self, pipeline):
        """Test bid amount calculation for low confidence."""
        amount = pipeline._calculate_bid_amount(
            budget_cents=10000,
            confidence=0.5,
            strategy=ExecutionStrategy.BALANCED,
        )
        
        # Should bid 40% of budget for low confidence
        assert amount == 4000

    def test_calculate_bid_amount_aggressive_strategy(self, pipeline):
        """Test bid amount with aggressive strategy."""
        amount = pipeline._calculate_bid_amount(
            budget_cents=10000,
            confidence=0.7,
            strategy=ExecutionStrategy.AGGRESSIVE,
        )
        
        # Aggressive should bid more
        assert amount > 6000

    def test_calculate_bid_amount_conservative_strategy(self, pipeline):
        """Test bid amount with conservative strategy."""
        amount = pipeline._calculate_bid_amount(
            budget_cents=10000,
            confidence=0.7,
            strategy=ExecutionStrategy.CONSERVATIVE,
        )
        
        # Conservative should bid less
        assert amount < 6000

    def test_calculate_bid_amount_limits(self, pipeline):
        """Test bid amount respects limits."""
        # Test max limit
        amount_max = pipeline._calculate_bid_amount(
            budget_cents=1000000,  # Very large budget
            confidence=0.9,
            strategy=ExecutionStrategy.BALANCED,
        )
        assert amount_max <= pipeline.max_bid_amount_cents
        
        # Test min limit
        amount_min = pipeline._calculate_bid_amount(
            budget_cents=100,  # Very small budget
            confidence=0.9,
            strategy=ExecutionStrategy.BALANCED,
        )
        assert amount_min >= 100

    @pytest.mark.asyncio
    async def test_place_bid_success(self, pipeline):
        """Test placing bid successfully."""
        opportunity = {
            "title": "Test Task",
            "marketplace": "test",
        }
        
        mock_db = MagicMock()
        mock_bid = MagicMock()
        mock_bid.id = "bid_123"
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()
        
        with patch('src.agent_execution.auto_execution.Bid') as mock_bid_class:
            mock_bid_class.return_value = mock_bid
            
            result = await pipeline._place_bid(
                opportunity=opportunity,
                amount_cents=10000,
                db=mock_db,
            )
            
            assert result["success"] is True
            assert result["bid_id"] == "bid_123"
            assert result["amount_cents"] == 10000

    @pytest.mark.asyncio
    async def test_place_bid_failure(self, pipeline):
        """Test placing bid fails."""
        opportunity = {"title": "Test"}
        mock_db = MagicMock()
        mock_db.add = MagicMock(side_effect=Exception("DB error"))
        mock_db.commit = MagicMock()
        mock_db.rollback = MagicMock()
        
        result = await pipeline._place_bid(
            opportunity=opportunity,
            amount_cents=10000,
            db=mock_db,
        )
        
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_with_retries_success(self, pipeline):
        """Test task execution with retries - success on first try."""
        task_data = {"title": "Test"}
        
        with patch.object(pipeline.task_router, 'route_task', AsyncMock()) as mock_route:
            mock_route.return_value = "Task result"
            
            result = await pipeline._execute_with_retries(
                task_data=task_data,
                task_id="task_123",
                domain="general",
            )
            
            assert result["success"] is True
            assert result["output"] == "Task result"
            assert result["metadata"]["attempts"] == 1

    @pytest.mark.asyncio
    async def test_execute_with_retries_failure(self, pipeline):
        """Test task execution with retries - all fail."""
        task_data = {"title": "Test"}
        
        with patch.object(pipeline.task_router, 'route_task', AsyncMock()) as mock_route:
            mock_route.side_effect = Exception("Execution failed")
            
            result = await pipeline._execute_with_retries(
                task_data=task_data,
                task_id="task_123",
                domain="general",
            )
            
            assert result["success"] is False
            assert "error" in result
            assert result["metadata"]["attempts"] == pipeline.retry_attempts

    def test_get_stats(self, pipeline):
        """Test getting execution statistics."""
        pipeline._execution_count = 10
        pipeline._success_count = 8
        pipeline._total_revenue_cents = 100000
        
        stats = pipeline.get_stats()
        
        assert stats["total_executions"] == 10
        assert stats["successful_executions"] == 8
        assert stats["success_rate"] == "80.00%"
        assert stats["total_revenue_dollars"] == 1000.0
        assert stats["strategy"] == "balanced"


class TestAutoExecutionPipelineGlobal:
    """Test global auto-execution pipeline."""

    def test_get_auto_execution_pipeline(self):
        """Test getting global pipeline."""
        pipeline = get_auto_execution_pipeline()
        assert pipeline is not None
        assert isinstance(pipeline, AutoExecutionPipeline)

    def test_reset_auto_execution_pipeline(self):
        """Test resetting global pipeline."""
        get_auto_execution_pipeline()
        reset_auto_execution_pipeline()
        pipeline = get_auto_execution_pipeline()
        assert pipeline is not None
