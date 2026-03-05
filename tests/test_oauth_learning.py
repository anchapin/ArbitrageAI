"""
Tests for OAuth Manager and Closed-Loop Learning System

Issue #105: Marketplace API Integration - OAuth Flow
Issue #106: Closed-Loop Learning System
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.agent_execution.marketplace_adapters.oauth_manager import (
    OAuthToken,
    OAuthManager,
    OAuthTokenStorage,
    get_oauth_manager,
    create_oauth_manager,
    get_token_storage,
)

from src.agent_execution.closed_loop_learning import (
    ClosedLoopLearningSystem,
    LearningEventType,
    LearningEntry,
    get_learning_system,
    reset_learning_system,
)


# =============================================================================
# OAuth Token Tests
# =============================================================================


class TestOAuthToken:
    """Test OAuth token functionality."""

    def test_token_creation(self):
        """Test OAuth token creation."""
        token = OAuthToken(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_in=3600,
            token_type="Bearer",
            scope="all",
        )

        assert token.access_token == "test_access_token"
        assert token.refresh_token == "test_refresh_token"
        assert token.expires_in == 3600
        assert token.token_type == "Bearer"
        assert token.scope == "all"

    def test_token_expiration(self):
        """Test token expiration detection."""
        # Create token that expires in 1 hour
        token = OAuthToken(
            access_token="test",
            refresh_token="test",
            expires_in=3600,
        )

        # Should not be expired yet
        assert not token.is_expired(buffer_seconds=60)

        # Create token that's already expired
        expired_token = OAuthToken(
            access_token="test",
            refresh_token="test",
            expires_in=60,  # Expires in 1 minute
        )

        # Manually set creation time to 2 minutes ago (use timezone-aware datetime)
        expired_token.created_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        expired_token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

        assert expired_token.is_expired(buffer_seconds=60)

    def test_token_to_dict(self):
        """Test token serialization."""
        token = OAuthToken(
            access_token="test_access",
            refresh_token="test_refresh",
            expires_in=3600,
        )

        token_dict = token.to_dict()

        assert token_dict["access_token"] == "test_access"
        assert token_dict["refresh_token"] == "test_refresh"
        assert token_dict["expires_in"] == 3600

    def test_token_from_dict(self):
        """Test token deserialization."""
        token_data = {
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "expires_in": 7200,
            "token_type": "Bearer",
            "scope": "all",
        }

        token = OAuthToken.from_dict(token_data)

        assert token.access_token == "test_access"
        assert token.refresh_token == "test_refresh"
        assert token.expires_in == 7200
        assert token.token_type == "Bearer"


# =============================================================================
# OAuth Manager Tests
# =============================================================================


class TestOAuthManager:
    """Test OAuth manager functionality."""

    def test_manager_creation(self):
        """Test OAuth manager creation."""
        manager = OAuthManager(
            platform="upwork",
            client_id="test_client_id",
            client_secret="test_client_secret",
        )

        assert manager.platform == "upwork"
        assert manager.client_id == "test_client_id"
        assert manager.client_secret == "test_client_secret"

    def test_unsupported_platform(self):
        """Test creation with unsupported platform."""
        with pytest.raises(ValueError, match="Unsupported platform"):
            OAuthManager(
                platform="invalid_platform",
                client_id="test",
                client_secret="test",
            )

    def test_generate_authorization_url(self):
        """Test authorization URL generation."""
        manager = OAuthManager(
            platform="upwork",
            client_id="test_client_id",
            client_secret="test_client_secret",
        )

        auth_url = manager.generate_authorization_url()

        assert "https://www.upwork.com/services/api/auth" in auth_url
        assert "client_id=test_client_id" in auth_url
        assert "response_type=code" in auth_url
        assert "scope=all" in auth_url
        assert "state=" in auth_url  # CSRF protection state parameter

    def test_generate_authorization_url_custom_params(self):
        """Test authorization URL with custom parameters."""
        manager = OAuthManager(
            platform="upwork",
            client_id="test_client_id",
            client_secret="test_client_secret",
        )

        auth_url = manager.generate_authorization_url(
            redirect_uri="https://example.com/callback",
            scope="custom_scope",
            state="custom_state",
        )

        assert "redirect_uri=https%3A%2F%2Fexample.com%2Fcallback" in auth_url
        assert "scope=custom_scope" in auth_url
        assert "state=custom_state" in auth_url

    def test_set_and_get_token(self):
        """Test token storage and retrieval."""
        manager = OAuthManager(
            platform="upwork",
            client_id="test",
            client_secret="test",
        )

        token = OAuthToken(
            access_token="test_token",
            refresh_token="test_refresh",
            expires_in=3600,
        )

        manager.set_token(token)
        retrieved_token = manager.get_token()

        assert retrieved_token == token
        assert retrieved_token.access_token == "test_token"

    def test_get_authorization_header(self):
        """Test authorization header generation."""
        manager = OAuthManager(
            platform="upwork",
            client_id="test",
            client_secret="test",
        )

        token = OAuthToken(
            access_token="test_token",
            refresh_token="test_refresh",
            expires_in=3600,
        )

        manager.set_token(token)
        auth_header = manager.get_authorization_header()

        assert auth_header == "Bearer test_token"

    def test_get_authorization_header_no_token(self):
        """Test authorization header without token."""
        manager = OAuthManager(
            platform="upwork",
            client_id="test",
            client_secret="test",
        )

        with pytest.raises(ValueError, match="No token available"):
            manager.get_authorization_header()

    def test_revoke_token(self):
        """Test token revocation."""
        manager = OAuthManager(
            platform="upwork",
            client_id="test",
            client_secret="test",
        )

        token = OAuthToken(
            access_token="test_token",
            refresh_token="test_refresh",
            expires_in=3600,
        )

        manager.set_token(token)
        assert manager.get_token() is not None

        manager.revoke_token()
        assert manager.get_token() is None


# =============================================================================
# OAuth Token Storage Tests
# =============================================================================


class TestOAuthTokenStorage:
    """Test OAuth token storage functionality."""

    def test_store_and_retrieve(self):
        """Test storing and retrieving tokens."""
        storage = OAuthTokenStorage()

        token = OAuthToken(
            access_token="upwork_token",
            refresh_token="upwork_refresh",
            expires_in=3600,
        )

        storage.store("upwork", token)
        retrieved = storage.retrieve("upwork")

        assert retrieved == token
        assert retrieved.access_token == "upwork_token"

    def test_delete_token(self):
        """Test deleting tokens."""
        storage = OAuthTokenStorage()

        token = OAuthToken(
            access_token="test_token",
            refresh_token="test_refresh",
            expires_in=3600,
        )

        storage.store("upwork", token)
        assert storage.retrieve("upwork") is not None

        deleted = storage.delete("upwork")
        assert deleted is True
        assert storage.retrieve("upwork") is None

    def test_delete_nonexistent_token(self):
        """Test deleting nonexistent token."""
        storage = OAuthTokenStorage()

        deleted = storage.delete("nonexistent")
        assert deleted is False

    def test_list_platforms(self):
        """Test listing platforms with stored tokens."""
        storage = OAuthTokenStorage()

        storage.store("upwork", MagicMock())
        storage.store("fiverr", MagicMock())
        storage.store("peopleperhour", MagicMock())

        platforms = storage.list_platforms()

        assert len(platforms) == 3
        assert "upwork" in platforms
        assert "fiverr" in platforms
        assert "peopleperhour" in platforms

    def test_clear_all(self):
        """Test clearing all tokens."""
        storage = OAuthTokenStorage()

        storage.store("upwork", MagicMock())
        storage.store("fiverr", MagicMock())

        storage.clear_all()

        assert len(storage.list_platforms()) == 0


# =============================================================================
# Closed-Loop Learning System Tests
# =============================================================================


class TestClosedLoopLearningSystem:
    """Test closed-loop learning system functionality."""

    @pytest.fixture
    def learning_system(self):
        """Create learning system instance."""
        from src.api.database import SessionLocal
        from src.api.models import LearningEntry
        
        reset_learning_system()
        ls = get_learning_system()
        
        # Clean up any existing learning entries before test
        db = SessionLocal()
        try:
            db.query(LearningEntry).delete()
            db.commit()
        finally:
            db.close()
        
        return ls

    def test_learning_system_initialization(self, learning_system):
        """Test learning system initialization."""
        assert learning_system is not None
        assert learning_system.confidence_tracker is not None
        assert learning_system.adjustment_algorithm is not None

    def test_record_job_completion(self, learning_system):
        """Test recording job completion."""
        entry = learning_system.record_job_completion(
            task_id="test_task_123",
            marketplace="upwork",
            revenue_cents=50000,  # $500
            total_cost_cents=10000,  # $100
            predicted_profit_cents=35000,  # $350
            initial_confidence_score=65,
            strategy_type="balanced",
            metadata={"job_type": "web_development"},
        )

        assert entry is not None
        assert entry.task_id == "test_task_123"
        assert entry.marketplace == "upwork"
        assert entry.actual_profit_cents == 40000  # $400
        assert entry.prediction_error_cents == 5000  # Overestimated by $50
        assert entry.initial_confidence_score == 65

    def test_record_job_completion_loss(self, learning_system):
        """Test recording job with loss."""
        entry = learning_system.record_job_completion(
            task_id="test_task_456",
            marketplace="fiverr",
            revenue_cents=5000,  # $50
            total_cost_cents=10000,  # $100
            predicted_profit_cents=10000,  # $100
            initial_confidence_score=70,
            strategy_type="aggressive",
        )

        assert entry is not None
        assert entry.actual_profit_cents == -5000  # Lost $50
        assert entry.prediction_error_cents == -15000  # Underestimated loss by $150

    def test_calculate_prediction_accuracy(self, learning_system):
        """Test prediction accuracy calculation."""
        # Record multiple job completions
        for i in range(20):
            learning_system.record_job_completion(
                task_id=f"test_task_{i}",
                marketplace="upwork",
                revenue_cents=50000,
                total_cost_cents=10000,
                predicted_profit_cents=35000 + (i * 1000),
                initial_confidence_score=65,
            )

        accuracy = learning_system.calculate_prediction_accuracy(
            marketplace="upwork",
            limit=50,
        )

        assert "total_entries" in accuracy
        assert accuracy["total_entries"] == 20
        assert "accuracy_rate" in accuracy
        assert "average_error_percentage" in accuracy

    def test_calculate_prediction_accuracy_no_data(self, learning_system):
        """Test accuracy calculation with no data."""
        accuracy = learning_system.calculate_prediction_accuracy(
            marketplace="nonexistent",
        )

        assert "error" in accuracy or accuracy.get("total_entries", 0) == 0

    def test_get_learning_insights(self, learning_system):
        """Test learning insights generation."""
        # Record some job completions
        for i in range(15):
            learning_system.record_job_completion(
                task_id=f"test_task_{i}",
                marketplace="upwork",
                revenue_cents=50000,
                total_cost_cents=10000,
                predicted_profit_cents=35000,
                initial_confidence_score=65,
            )

        insights = learning_system.get_learning_insights(marketplace="upwork")

        assert "insights" in insights
        assert "recommendations" in insights
        assert "accuracy_metrics" in insights

    def test_weekly_review(self, learning_system):
        """Test weekly review functionality."""
        # Record some job completions
        for i in range(10):
            learning_system.record_job_completion(
                task_id=f"test_task_{i}",
                marketplace="upwork" if i % 2 == 0 else "fiverr",
                revenue_cents=50000,
                total_cost_cents=10000,
                predicted_profit_cents=35000,
                initial_confidence_score=65,
                strategy_type="balanced" if i % 2 == 0 else "aggressive",
            )

        review = learning_system.perform_weekly_review()

        assert review["status"] == "success"
        assert "total_jobs_analyzed" in review
        assert "marketplace_performance" in review
        assert "strategy_performance" in review
        assert "recommendations" in review

    def test_get_learning_history(self, learning_system):
        """Test learning history retrieval."""
        # Disable automatic weekly review during this test
        learning_system._last_weekly_review = datetime.now(timezone.utc)
        
        # Record some job completions
        for i in range(5):
            learning_system.record_job_completion(
                task_id=f"test_task_{i}",
                marketplace="upwork",
                revenue_cents=50000,
                total_cost_cents=10000,
                predicted_profit_cents=35000,
                initial_confidence_score=65,
            )

        history = learning_system.get_learning_history(limit=10)

        # Should have 5 new entries
        assert len(history) == 5
        # Verify our new entries are present
        test_tasks = [e for e in history if e.task_id.startswith("test_task_")]
        assert len(test_tasks) == 5

    def test_get_learning_history_filter(self, learning_system):
        """Test learning history with filters."""
        # Record job completions for different marketplaces
        for i in range(5):
            learning_system.record_job_completion(
                task_id=f"upwork_task_{i}",
                marketplace="upwork",
                revenue_cents=50000,
                total_cost_cents=10000,
                predicted_profit_cents=35000,
                initial_confidence_score=65,
            )

        for i in range(3):
            learning_system.record_job_completion(
                task_id=f"fiverr_task_{i}",
                marketplace="fiverr",
                revenue_cents=50000,
                total_cost_cents=10000,
                predicted_profit_cents=35000,
                initial_confidence_score=65,
            )

        # Filter by marketplace
        upwork_history = learning_system.get_learning_history(
            marketplace="upwork",
            limit=10,
        )

        assert len(upwork_history) == 5
        assert all(entry.marketplace == "upwork" for entry in upwork_history)


# =============================================================================
# Integration Tests
# =============================================================================


class TestOAuthManagerIntegration:
    """Integration tests for OAuth manager."""

    @pytest.mark.asyncio
    async def test_full_oauth_flow(self):
        """Test complete OAuth flow (mocked)."""
        # Create manager
        manager = create_oauth_manager(
            platform="upwork",
            client_id="test_client_id",
            client_secret="test_client_secret",
        )

        # Generate authorization URL
        auth_url = manager.generate_authorization_url()
        assert "state=" in auth_url

        # Extract state from URL
        state = auth_url.split("state=")[1].split("&")[0]

        # Mock token exchange - patch httpx to avoid network call
        mock_token_data = {
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        # Create a proper async mock
        async def mock_post(*args, **kwargs):
            class MockResponse:
                def json(self):
                    return mock_token_data
                def raise_for_status(self):
                    return None
            return MockResponse()

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            token = await manager.exchange_code_for_token("auth_code", state)

            assert token.access_token == "mock_access_token"
            assert manager.get_token() == token

        # Store token
        storage = get_token_storage()
        storage.store("upwork", token)

        # Retrieve token
        retrieved = storage.retrieve("upwork")
        assert retrieved == token


class TestLearningSystemIntegration:
    """Integration tests for learning system."""

    def test_continuous_learning_loop(self):
        """Test continuous learning from multiple jobs."""
        reset_learning_system()
        system = get_learning_system()

        # Simulate multiple job completions
        job_results = [
            {"revenue": 50000, "cost": 10000, "predicted": 35000},  # Profitable
            {"revenue": 30000, "cost": 10000, "predicted": 25000},  # Profitable
            {"revenue": 5000, "cost": 10000, "predicted": 10000},   # Loss
            {"revenue": 60000, "cost": 15000, "predicted": 40000},  # Profitable
            {"revenue": 20000, "cost": 10000, "predicted": 15000},  # Profitable
        ]

        for i, result in enumerate(job_results):
            system.record_job_completion(
                task_id=f"job_{i}",
                marketplace="upwork",
                revenue_cents=result["revenue"],
                total_cost_cents=result["cost"],
                predicted_profit_cents=result["predicted"],
                initial_confidence_score=65,
                strategy_type="balanced",
            )

        # Get insights after learning
        insights = system.get_learning_insights(marketplace="upwork")

        assert len(insights["insights"]) >= 0  # May or may not have insights
        assert "accuracy_metrics" in insights
        assert insights["accuracy_metrics"]["total_entries"] >= 5

    def test_marketplace_comparison(self):
        """Test learning across multiple marketplaces."""
        reset_learning_system()
        system = get_learning_system()

        # Record jobs for different marketplaces
        marketplaces = ["upwork", "fiverr", "peopleperhour"]

        for mp in marketplaces:
            for i in range(5):
                system.record_job_completion(
                    task_id=f"{mp}_job_{i}",
                    marketplace=mp,
                    revenue_cents=50000,
                    total_cost_cents=10000,
                    predicted_profit_cents=35000,
                    initial_confidence_score=65,
                )

        # Get accuracy for each marketplace
        for mp in marketplaces:
            accuracy = system.calculate_prediction_accuracy(marketplace=mp)
            assert accuracy["total_entries"] == 5


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_oauth_token_buffer_expiration(self):
        """Test token expiration with buffer."""
        token = OAuthToken(
            access_token="test",
            refresh_token="test",
            expires_in=300,  # 5 minutes
        )

        # Set expiration to 4 minutes from now
        token.expires_at = datetime.now(timezone.utc) + timedelta(minutes=4)

        # Should be expired with 5-minute buffer
        assert token.is_expired(buffer_seconds=300)

    def test_learning_system_zero_predictions(self):
        """Test learning system with zero predictions."""
        reset_learning_system()
        system = get_learning_system()

        # Record job with zero predicted profit
        entry = system.record_job_completion(
            task_id="zero_pred",
            marketplace="upwork",
            revenue_cents=10000,
            total_cost_cents=5000,
            predicted_profit_cents=0,
            initial_confidence_score=50,
        )

        assert entry is not None
        # Should handle division by zero gracefully
        assert entry.prediction_error_percentage is not None

    def test_oauth_manager_state_mismatch(self):
        """Test OAuth state mismatch detection."""
        manager = OAuthManager(
            platform="upwork",
            client_id="test",
            client_secret="test",
        )

        # Generate auth URL with one state
        manager.generate_authorization_url(state="state1")

        # Try to exchange code with different state
        with pytest.raises(ValueError, match="CSRF"):
            asyncio.run(manager.exchange_code_for_token("code", "state2"))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
