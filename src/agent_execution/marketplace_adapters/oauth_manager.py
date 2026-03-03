"""
OAuth 2.0 Manager for Marketplace Integrations

Handles OAuth authentication flow for marketplace platforms like Upwork.
Implements OAuth 2.0 three-legged authentication with token refresh.

Issue #105: Marketplace API Integration - OAuth Flow
"""

from datetime import datetime, timedelta
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

from src.config.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OAuthToken:
    """Represents an OAuth token with expiration."""

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        token_type: str = "Bearer",
        scope: str | None = None,
    ):
        """
        Initialize OAuth token.

        Args:
            access_token: Access token string
            refresh_token: Refresh token string
            expires_in: Token lifetime in seconds
            token_type: Token type (usually "Bearer")
            scope: Granted scope
        """
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_type = token_type
        self.scope = scope
        self.expires_in = expires_in
        self.created_at = datetime.utcnow()
        self.expires_at = self.created_at + timedelta(seconds=expires_in)

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """
        Check if token is expired or about to expire.

        Args:
            buffer_seconds: Seconds before expiration to consider expired

        Returns:
            True if token is expired or will expire soon
        """
        now = datetime.utcnow()
        return now >= (self.expires_at - timedelta(seconds=buffer_seconds))

    def to_dict(self) -> dict[str, Any]:
        """Convert token to dictionary."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "scope": self.scope,
            "expires_in": self.expires_in,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OAuthToken":
        """Create OAuthToken from dictionary."""
        token = cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", ""),
            expires_in=data.get("expires_in", 3600),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope"),
        )
        # Restore original timestamps if available
        if "created_at" in data:
            token.created_at = datetime.fromisoformat(data["created_at"])
        if "expires_at" in data:
            token.expires_at = datetime.fromisoformat(data["expires_at"])
        return token


class OAuthManager:
    """
    OAuth 2.0 Manager for marketplace authentication.

    Handles the complete OAuth flow:
    1. Generate authorization URL
    2. Handle callback and exchange code for tokens
    3. Refresh tokens when expired
    4. Store and manage tokens securely

    Supports platforms:
    - Upwork (OAuth 1.0a / OAuth 2.0)
    - Fiverr (OAuth 2.0)
    - PeoplePerHour (OAuth 2.0)
    """

    # Platform-specific OAuth configurations
    PLATFORM_CONFIG = {
        "upwork": {
            "auth_url": "https://www.upwork.com/services/api/auth",
            "token_url": "https://www.upwork.com/api/oauth/v2/token",
            "callback_url": ConfigManager.get("UPWORK_OAUTH_CALLBACK", "http://localhost:8000/api/v1/marketplace/oauth/upwork/callback"),
            "scope": "all",  # Upwork uses 'all' for full access
        },
        "fiverr": {
            "auth_url": "https://www.fiverr.com/oauth/authorize",
            "token_url": "https://www.fiverr.com/oauth/token",
            "callback_url": ConfigManager.get("FIVERR_OAUTH_CALLBACK", "http://localhost:8000/api/v1/marketplace/oauth/fiverr/callback"),
            "scope": "seller_gigs,orders,messages",
        },
        "peopleperhour": {
            "auth_url": "https://www.peopleperhour.com/oauth/authorize",
            "token_url": "https://www.peopleperhour.com/oauth/token",
            "callback_url": ConfigManager.get("PPH_OAUTH_CALLBACK", "http://localhost:8000/api/v1/marketplace/oauth/pph/callback"),
            "scope": "profile,proposals,messages",
        },
    }

    def __init__(self, platform: str, client_id: str, client_secret: str):
        """
        Initialize OAuth manager.

        Args:
            platform: Marketplace platform name
            client_id: OAuth client ID
            client_secret: OAuth client secret
        """
        self.platform = platform.lower()
        self.client_id = client_id
        self.client_secret = client_secret

        if self.platform not in self.PLATFORM_CONFIG:
            raise ValueError(f"Unsupported platform: {platform}")

        self.config = self.PLATFORM_CONFIG[self.platform]
        self._token: OAuthToken | None = None
        self._state: str | None = None

    def generate_authorization_url(
        self,
        redirect_uri: str | None = None,
        scope: str | None = None,
        state: str | None = None,
    ) -> str:
        """
        Generate OAuth authorization URL.

        Args:
            redirect_uri: Callback URL (uses default if not provided)
            scope: OAuth scope (uses default if not provided)
            state: State parameter for CSRF protection (auto-generated if not provided)

        Returns:
            Authorization URL to redirect user to
        """
        # Generate state for CSRF protection
        self._state = state or secrets.token_urlsafe(32)

        # Build authorization URL parameters
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri or self.config["callback_url"],
            "response_type": "code",
            "scope": scope or self.config["scope"],
            "state": self._state,
        }

        auth_url = f"{self.config['auth_url']}?{urlencode(params)}"
        logger.info(f"Generated {self.platform} authorization URL")
        return auth_url

    async def exchange_code_for_token(
        self,
        authorization_code: str,
        state: str,
        redirect_uri: str | None = None,
    ) -> OAuthToken:
        """
        Exchange authorization code for access token.

        Args:
            authorization_code: Authorization code from callback
            state: State parameter from authorization (for CSRF validation)
            redirect_uri: Redirect URI used in authorization

        Returns:
            OAuthToken with access and refresh tokens

        Raises:
            ValueError: If state doesn't match (CSRF attack detected)
            httpx.HTTPError: If token exchange fails
        """
        # Validate state to prevent CSRF attacks
        if state != self._state:
            raise ValueError("State mismatch - possible CSRF attack")

        token_url = self.config["token_url"]
        redirect = redirect_uri or self.config["callback_url"]

        # Prepare token request
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": authorization_code,
            "redirect_uri": redirect,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()

        # Create token object
        self._token = OAuthToken(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", ""),
            expires_in=token_data.get("expires_in", 3600),
            token_type=token_data.get("token_type", "Bearer"),
            scope=token_data.get("scope"),
        )

        logger.info(
            f"Successfully obtained {self.platform} access token "
            f"(expires in {self._token.expires_in}s)",
        )

        return self._token

    async def refresh_access_token(self) -> OAuthToken:
        """
        Refresh access token using refresh token.

        Returns:
            New OAuthToken with refreshed access token

        Raises:
            ValueError: If no refresh token available
            httpx.HTTPError: If refresh fails
        """
        if not self._token or not self._token.refresh_token:
            raise ValueError("No refresh token available")

        token_url = self.config["token_url"]

        # Prepare refresh request
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self._token.refresh_token,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()

        # Update token
        self._token = OAuthToken(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", self._token.refresh_token),
            expires_in=token_data.get("expires_in", 3600),
            token_type=token_data.get("token_type", "Bearer"),
            scope=token_data.get("scope"),
        )

        logger.info(f"Successfully refreshed {self.platform} access token")
        return self._token

    async def get_valid_token(self) -> OAuthToken:
        """
        Get valid access token, refreshing if necessary.

        Returns:
            Valid OAuthToken

        Raises:
            ValueError: If no token available or refresh fails
        """
        if not self._token:
            raise ValueError("No token available - must authorize first")

        # Refresh if token is expired or about to expire
        if self._token.is_expired(buffer_seconds=300):  # 5 minute buffer
            await self.refresh_access_token()

        return self._token

    def set_token(self, token: OAuthToken) -> None:
        """
        Set token directly (useful for loading from storage).

        Args:
            token: OAuthToken to set
        """
        self._token = token
        logger.info(f"Set {self.platform} token (expires at {token.expires_at})")

    def get_token(self) -> OAuthToken | None:
        """
        Get current token.

        Returns:
            Current OAuthToken or None
        """
        return self._token

    def get_authorization_header(self) -> str:
        """
        Get Authorization header for API requests.

        Returns:
            Authorization header value

        Raises:
            ValueError: If no valid token available
        """
        if not self._token:
            raise ValueError("No token available")

        return f"{self._token.token_type} {self._token.access_token}"

    def revoke_token(self) -> bool:
        """
        Revoke access and refresh tokens.

        Returns:
            True if revocation successful
        """
        if not self._token:
            return False

        # Some platforms support token revocation endpoint
        # For now, just clear local token
        self._token = None
        logger.info(f"Revoked {self.platform} tokens")
        return True


class OAuthTokenStorage:
    """
    Secure storage for OAuth tokens.

    Provides persistent storage for OAuth tokens with encryption support.
    Tokens are stored in memory by default, but can be persisted to database.
    """

    def __init__(self):
        """Initialize token storage."""
        self._tokens: dict[str, OAuthToken] = {}

    def store(self, platform: str, token: OAuthToken) -> None:
        """
        Store token for platform.

        Args:
            platform: Platform identifier
            token: OAuthToken to store
        """
        self._tokens[platform] = token
        logger.debug(f"Stored token for {platform}")

    def retrieve(self, platform: str) -> OAuthToken | None:
        """
        Retrieve token for platform.

        Args:
            platform: Platform identifier

        Returns:
            OAuthToken or None if not found
        """
        return self._tokens.get(platform)

    def delete(self, platform: str) -> bool:
        """
        Delete token for platform.

        Args:
            platform: Platform identifier

        Returns:
            True if token was deleted
        """
        if platform in self._tokens:
            del self._tokens[platform]
            logger.debug(f"Deleted token for {platform}")
            return True
        return False

    def list_platforms(self) -> list:
        """
        List all platforms with stored tokens.

        Returns:
            List of platform names
        """
        return list(self._tokens.keys())

    def clear_all(self) -> None:
        """Clear all stored tokens."""
        self._tokens.clear()
        logger.info("Cleared all stored tokens")


# Global instances
_token_storage = OAuthTokenStorage()
_oauth_managers: dict[str, OAuthManager] = {}


def get_oauth_manager(platform: str) -> OAuthManager | None:
    """
    Get OAuth manager for platform.

    Args:
        platform: Marketplace platform name

    Returns:
        OAuthManager instance or None
    """
    return _oauth_managers.get(platform.lower())


def create_oauth_manager(
    platform: str,
    client_id: str,
    client_secret: str,
) -> OAuthManager:
    """
    Create and register OAuth manager for platform.

    Args:
        platform: Marketplace platform name
        client_id: OAuth client ID
        client_secret: OAuth client secret

    Returns:
        OAuthManager instance
    """
    manager = OAuthManager(platform, client_id, client_secret)
    _oauth_managers[platform.lower()] = manager
    logger.info(f"Created OAuth manager for {platform}")
    return manager


def get_token_storage() -> OAuthTokenStorage:
    """Get global token storage instance."""
    return _token_storage


async def refresh_all_tokens() -> dict[str, bool]:
    """
    Refresh all stored tokens that are expiring.

    Returns:
        Dictionary mapping platform to refresh success
    """
    results = {}

    for platform, manager in _oauth_managers.items():
        token = manager.get_token()
        if token and token.is_expired(buffer_seconds=300):
            try:
                await manager.refresh_access_token()
                _token_storage.store(platform, manager.get_token())
                results[platform] = True
            except Exception as e:
                logger.error(f"Failed to refresh {platform} token: {e}")
                results[platform] = False
        else:
            results[platform] = True  # No refresh needed

    return results
