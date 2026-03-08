"""
Tests for OAuth Manager (Issue #105)

Tests OAuth authentication flow for marketplace integrations:
1. Generate authorization URL
2. Exchange code for token
3. Refresh access token
4. Token storage and management
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, Mock
import httpx

from src.agent_execution.marketplace_adapters.oauth_manager import (
    OAuthManager,
    OAuthToken,
    OAuthTokenStorage,
    get_oauth_manager,
    create_oauth_manager,
    get_token_storage,
    refresh_all_tokens,
)


@pytest.fixture(autouse=True)
def reset_oauth_state():
    """Reset OAuth state before each test."""
    # Clear any existing managers
    from src.agent_execution.marketplace_adapters import oauth_manager

    oauth_manager._oauth_managers.clear()
    oauth_manager._token_storage.clear_all()
    yield


@pytest.fixture
def oauth_manager():
    """Create OAuth manager for testing."""
    return OAuthManager(
        platform="upwork",
        client_id="test_client_id",
        client_secret="test_client_secret",
    )


@pytest.fixture
def sample_token():
    """Create a sample OAuth token."""
    return OAuthToken(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        expires_in=3600,
        token_type="Bearer",
        scope="all",
    )


class TestOAuthToken:
    """Test OAuthToken class."""

    def test_token_creation(self, sample_token):
        """Test creating OAuth token."""
        assert sample_token.access_token == "test_access_token"
        assert sample_token.refresh_token == "test_refresh_token"
        assert sample_token.expires_in == 3600
        assert sample_token.token_type == "Bearer"
        assert sample_token.scope == "all"

    def test_token_not_expired(self, sample_token):
        """Test token expiration check - not expired."""
        assert sample_token.is_expired() is False
        # Token expires in 1 hour, so with 3600s buffer it will be considered expired
        # Use smaller buffer to test not expired
        assert sample_token.is_expired(buffer_seconds=300) is False

    def test_token_expired(self):
        """Test token expiration check - expired."""
        # Create token that expires in 1 second
        token = OAuthToken(
            access_token="test",
            refresh_token="test",
            expires_in=1,
        )
        # Manually set expiration to past
        token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)

        assert token.is_expired() is True

    def test_token_to_dict(self, sample_token):
        """Test converting token to dictionary."""
        token_dict = sample_token.to_dict()

        assert "access_token" in token_dict
        assert "refresh_token" in token_dict
        assert "expires_in" in token_dict
        assert token_dict["access_token"] == "test_access_token"
        assert token_dict["expires_in"] == 3600

    def test_token_from_dict(self):
        """Test creating token from dictionary."""
        token_data = {
            "access_token": "from_dict_token",
            "refresh_token": "refresh_123",
            "expires_in": 7200,
            "token_type": "Bearer",
            "scope": "read",
        }

        token = OAuthToken.from_dict(token_data)

        assert token.access_token == "from_dict_token"
        assert token.refresh_token == "refresh_123"
        assert token.expires_in == 7200
        assert token.token_type == "Bearer"

    def test_token_from_dict_with_timestamps(self):
        """Test creating token from dictionary with timestamps."""
        now = datetime.now(timezone.utc)
        token_data = {
            "access_token": "test",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
        }

        token = OAuthToken.from_dict(token_data)

        assert token.created_at == now
        assert token.expires_at == now + timedelta(hours=1)


class TestOAuthManager:
    """Test OAuthManager class."""

    def test_manager_creation(self, oauth_manager):
        """Test creating OAuth manager."""
        assert oauth_manager.platform == "upwork"
        assert oauth_manager.client_id == "test_client_id"
        assert oauth_manager.client_secret == "test_client_secret"
        assert oauth_manager._token is None

    def test_manager_unsupported_platform(self):
        """Test creating manager with unsupported platform."""
        with pytest.raises(ValueError) as exc_info:
            OAuthManager(
                platform="unsupported",
                client_id="test",
                client_secret="test",
            )

        assert "Unsupported platform" in str(exc_info.value)

    def test_generate_authorization_url(self, oauth_manager):
        """Test generating authorization URL."""
        auth_url = oauth_manager.generate_authorization_url()

        assert "https://www.upwork.com/services/api/auth" in auth_url
        assert "client_id=test_client_id" in auth_url
        assert "response_type=code" in auth_url
        assert "scope=all" in auth_url
        assert "state=" in auth_url

    def test_generate_authorization_url_custom_params(self, oauth_manager):
        """Test generating authorization URL with custom parameters."""
        auth_url = oauth_manager.generate_authorization_url(
            redirect_uri="https://custom.com/callback",
            scope="custom_scope",
            state="custom_state",
        )

        assert "redirect_uri=https%3A%2F%2Fcustom.com%2Fcallback" in auth_url
        assert "scope=custom_scope" in auth_url
        assert "state=custom_state" in auth_url

    @pytest.mark.asyncio
    async def test_exchange_code_for_token(self, oauth_manager):
        """Test exchanging authorization code for token."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "all",
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            # Generate auth URL to set state
            auth_url = oauth_manager.generate_authorization_url()
            state = auth_url.split("state=")[1].split("&")[0]

            # Exchange code
            token = await oauth_manager.exchange_code_for_token(
                authorization_code="test_auth_code",
                state=state,
            )

            assert token.access_token == "new_access_token"
            assert token.refresh_token == "new_refresh_token"
            assert token.expires_in == 3600

    @pytest.mark.asyncio
    async def test_exchange_code_invalid_state(self, oauth_manager):
        """Test exchanging code with invalid state (CSRF protection)."""
        # Generate auth URL to set state
        oauth_manager.generate_authorization_url()

        with pytest.raises(ValueError) as exc_info:
            await oauth_manager.exchange_code_for_token(
                authorization_code="test_code",
                state="invalid_state",
            )

        assert "CSRF" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_refresh_access_token(self, oauth_manager, sample_token):
        """Test refreshing access token."""
        # Set initial token
        oauth_manager.set_token(sample_token)

        # Mock refresh response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 7200,
            "token_type": "Bearer",
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            new_token = await oauth_manager.refresh_access_token()

            assert new_token.access_token == "refreshed_access_token"
            assert new_token.expires_in == 7200

    @pytest.mark.asyncio
    async def test_refresh_no_refresh_token(self, oauth_manager):
        """Test refreshing without refresh token."""
        with pytest.raises(ValueError) as exc_info:
            await oauth_manager.refresh_access_token()

        assert "No refresh token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_valid_token(self, oauth_manager, sample_token):
        """Test getting valid token."""
        oauth_manager.set_token(sample_token)

        token = await oauth_manager.get_valid_token()

        assert token.access_token == "test_access_token"
        assert token is not None

    @pytest.mark.asyncio
    async def test_get_valid_token_auto_refresh(self, oauth_manager):
        """Test that get_valid_token auto-refreshes expired token."""
        # Create expired token
        expired_token = OAuthToken(
            access_token="expired",
            refresh_token="refresh",
            expires_in=1,
        )
        expired_token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        oauth_manager.set_token(expired_token)

        # Mock refresh response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_token",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            token = await oauth_manager.get_valid_token()

            assert token.access_token == "new_token"

    def test_get_authorization_header(self, oauth_manager, sample_token):
        """Test getting authorization header."""
        oauth_manager.set_token(sample_token)

        auth_header = oauth_manager.get_authorization_header()

        assert auth_header == "Bearer test_access_token"

    def test_get_authorization_header_no_token(self, oauth_manager):
        """Test getting auth header without token."""
        with pytest.raises(ValueError) as exc_info:
            oauth_manager.get_authorization_header()

        assert "No token available" in str(exc_info.value)

    def test_revoke_token(self, oauth_manager, sample_token):
        """Test revoking token."""
        oauth_manager.set_token(sample_token)
        assert oauth_manager.get_token() is not None

        result = oauth_manager.revoke_token()

        assert result is True
        assert oauth_manager.get_token() is None


class TestOAuthTokenStorage:
    """Test OAuthTokenStorage class."""

    def test_store_and_retrieve(self):
        """Test storing and retrieving token."""
        storage = OAuthTokenStorage()
        token = OAuthToken(
            access_token="store_test",
            refresh_token="refresh",
            expires_in=3600,
        )

        storage.store("upwork", token)
        retrieved = storage.retrieve("upwork")

        assert retrieved is not None
        assert retrieved.access_token == "store_test"

    def test_retrieve_nonexistent(self):
        """Test retrieving nonexistent token."""
        storage = OAuthTokenStorage()
        token = storage.retrieve("nonexistent")

        assert token is None

    def test_delete(self):
        """Test deleting token."""
        storage = OAuthTokenStorage()
        token = OAuthToken(
            access_token="delete_test",
            refresh_token="refresh",
            expires_in=3600,
        )

        storage.store("fiverr", token)
        result = storage.delete("fiverr")

        assert result is True
        assert storage.retrieve("fiverr") is None

    def test_delete_nonexistent(self):
        """Test deleting nonexistent token."""
        storage = OAuthTokenStorage()
        result = storage.delete("nonexistent")

        assert result is False

    def test_list_platforms(self):
        """Test listing platforms."""
        storage = OAuthTokenStorage()

        token1 = OAuthToken("token1", "refresh1", 3600)
        token2 = OAuthToken("token2", "refresh2", 3600)

        storage.store("upwork", token1)
        storage.store("fiverr", token2)

        platforms = storage.list_platforms()

        assert "upwork" in platforms
        assert "fiverr" in platforms
        assert len(platforms) == 2

    def test_clear_all(self):
        """Test clearing all tokens."""
        storage = OAuthTokenStorage()

        storage.store("upwork", OAuthToken("t1", "r1", 3600))
        storage.store("fiverr", OAuthToken("t2", "r2", 3600))

        storage.clear_all()

        assert storage.list_platforms() == []


class TestOAuthManagerFunctions:
    """Test OAuth manager helper functions."""

    def test_create_oauth_manager(self):
        """Test creating OAuth manager via helper function."""
        manager = create_oauth_manager(
            platform="upwork",
            client_id="test_id",
            client_secret="test_secret",
        )

        assert manager is not None
        assert manager.platform == "upwork"

        # Verify it's registered
        retrieved = get_oauth_manager("upwork")
        assert retrieved is manager

    def test_get_oauth_manager_not_found(self):
        """Test getting nonexistent OAuth manager."""
        manager = get_oauth_manager("nonexistent")
        assert manager is None

    def test_get_token_storage(self):
        """Test getting token storage."""
        storage = get_token_storage()
        assert storage is not None
        assert isinstance(storage, OAuthTokenStorage)

    @pytest.mark.asyncio
    async def test_refresh_all_tokens(self):
        """Test refreshing all tokens."""
        # Create and register manager
        manager = create_oauth_manager(
            platform="upwork",
            client_id="test",
            client_secret="test",
        )

        # Set expired token
        expired_token = OAuthToken(
            access_token="expired",
            refresh_token="refresh",
            expires_in=1,
        )
        expired_token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        manager.set_token(expired_token)

        # Mock refresh response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            results = await refresh_all_tokens()

            assert "upwork" in results
            assert results["upwork"] is True

    @pytest.mark.asyncio
    async def test_refresh_all_tokens_no_refresh_needed(self):
        """Test refreshing when no refresh needed."""
        # Create and register manager
        manager = create_oauth_manager(
            platform="fiverr",
            client_id="test",
            client_secret="test",
        )

        # Set valid token
        valid_token = OAuthToken(
            access_token="valid",
            refresh_token="refresh",
            expires_in=3600,
        )
        manager.set_token(valid_token)

        results = await refresh_all_tokens()

        assert "fiverr" in results
        assert results["fiverr"] is True


class TestPlatformConfigurations:
    """Test platform-specific OAuth configurations."""

    def test_upwork_config(self, oauth_manager):
        """Test Upwork OAuth configuration."""
        config = oauth_manager.config

        assert "auth_url" in config
        assert "token_url" in config
        assert "callback_url" in config
        assert config["scope"] == "all"
        assert "upwork" in config["auth_url"]

    def test_fiverr_config(self):
        """Test Fiverr OAuth configuration."""
        manager = OAuthManager("fiverr", "client", "secret")
        config = manager.config

        assert "fiverr" in config["auth_url"]
        assert "fiverr" in config["token_url"]
        assert "seller" in config["scope"]

    def test_peopleperhour_config(self):
        """Test PeoplePerHour OAuth configuration."""
        manager = OAuthManager("peopleperhour", "client", "secret")
        config = manager.config

        assert "peopleperhour" in config["auth_url"]
        assert "peopleperhour" in config["token_url"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
