"""
API Versioning Utilities and Dependencies.

This module provides utilities for API versioning, including version detection,
validation, and deprecation handling.
"""
from enum import Enum
import logging
from typing import Annotated

from fastapi import Header, HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class APIVersion(str, Enum):
    """Supported API versions."""

    V1 = "v1"
    V2 = "v2"  # Future version


# Supported versions list
SUPPORTED_VERSIONS = [APIVersion.V1, APIVersion.V2]

# Deprecation configuration
DEPRECATION_HEADER = "Deprecation"
SUNSET_HEADER = "Sunset"
LINK_HEADER = "Link"
WARNING_HEADER = "Warning"


def get_api_version(
    x_api_version: Annotated[str | None, Header(alias="X-API-Version")] = None,
) -> APIVersion:
    """
    Extract and validate API version from request headers.

    Args:
        x_api_version: Optional API version from X-API-Version header.

    Returns:
        Validated APIVersion enum.

    Raises:
        HTTPException: If version is not supported.
    """
    if x_api_version is None:
        return APIVersion.V1

    # First check if it's a valid format
    if not isinstance(x_api_version, str) or not x_api_version.startswith("v"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_VERSION_FORMAT",
                "message": f"Invalid API version format: '{x_api_version}'",
                "supported_versions": [v.value for v in SUPPORTED_VERSIONS],
            },
        )

    try:
        version = APIVersion(x_api_version)
        if version not in SUPPORTED_VERSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "VERSION_NOT_SUPPORTED",
                    "message": f"API version '{x_api_version}' is not supported.",
                    "supported_versions": [v.value for v in SUPPORTED_VERSIONS],
                },
            )
        return version
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VERSION_NOT_SUPPORTED",
                "message": f"API version '{x_api_version}' is not supported.",
                "supported_versions": [v.value for v in SUPPORTED_VERSIONS],
            },
        ) from None


def add_deprecation_headers(
    response: Response,
    deprecated: bool = True,
    sunset_date: str | None = None,
    successor_version: str | None = None,
    warning_message: str | None = None,
) -> None:
    """
    Add deprecation headers to response.

    Args:
        response: FastAPI Response object.
        deprecated: Whether the endpoint is deprecated.
        sunset_date: Date when the endpoint will be removed (ISO 8601 format).
        successor_version: URL or version of the successor endpoint.
        warning_message: Custom deprecation warning message.

    Example:
        @router.get("/tasks")
        def get_tasks(response: Response):
            add_deprecation_headers(
                response,
                sunset_date="2027-06-30",
                successor_version="v2",
                warning_message="This endpoint is deprecated. Use /api/v2/tasks instead."
            )
            return tasks
    """
    if deprecated:
        response.headers[DEPRECATION_HEADER] = "true"

    if sunset_date:
        response.headers[SUNSET_HEADER] = sunset_date

    if successor_version:
        # RFC 5988 Link header format
        response.headers[LINK_HEADER] = (
            f'</api/{successor_version}>; rel="successor-version"'
        )

    if warning_message:
        # RFC 7234 Warning header format
        response.headers[WARNING_HEADER] = f'299 - "{warning_message}"'


def validate_version_supported(version: str) -> bool:
    """
    Check if an API version is supported.

    Args:
        version: Version string to validate.

    Returns:
        True if the version is supported, False otherwise.
    """
    return version in [v.value for v in SUPPORTED_VERSIONS]


def get_successor_version(version: APIVersion) -> APIVersion | None:
    """
    Get the successor version for a given API version.

    Args:
        version: Current API version.

    Returns:
        Successor API version, or None if this is the latest version.
    """
    version_order = {APIVersion.V1: APIVersion.V2}
    return version_order.get(version)


class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle API versioning from URL path.

    This middleware extracts the API version from the URL path (/api/v1/, /api/v2/, etc.)
    and validates it against supported versions. It also adds deprecation headers
    to responses for deprecated versions.

    Example:
        from fastapi import FastAPI
        from src.api.versioning import APIVersionMiddleware

        app = FastAPI()
        app.add_middleware(APIVersionMiddleware)
    """

    async def dispatch(self, request: Request, call_next):  # noqa: PLR6301
        """
        Process request and validate API version.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response with version headers
        """
        path = request.url.path

        # Extract version from path (/api/v1/..., /api/v2/..., etc.)
        version = APIVersionMiddleware._extract_version_from_path(path)

        if version:
            # Validate version is supported
            if not APIVersionMiddleware._is_version_supported(version):
                logger.warning(f"Unsupported API version requested: {version}")
                return Response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "error": "VERSION_NOT_SUPPORTED",
                        "message": f"API version '{version}' is not supported.",
                        "supported_versions": [v.value for v in SUPPORTED_VERSIONS],
                    },
                )

            # Log version usage for analytics
            logger.debug(f"API request version: {version} for path: {path}")

        # Process request
        response = await call_next(request)

        # Add version header to response
        if version:
            response.headers["X-API-Version"] = version

            # Add deprecation warning for v1 (when v2 becomes current)
            if version == APIVersion.V1.value and APIVersionMiddleware._is_version_deprecated(version):
                response.headers[DEPRECATION_HEADER] = "true"
                response.headers[WARNING_HEADER] = (
                    f'299 - "API version {version} is deprecated. '
                    f'Please use {APIVersion.V2.value} instead."'
                )

        return response

    @staticmethod
    def _extract_version_from_path(path: str) -> str | None:
        """
        Extract API version from URL path.

        Args:
            path: URL path (e.g., /api/v1/tasks)

        Returns:
            Version string (e.g., 'v1') or None if not found
        """
        import re

        # Match /api/v{number}/ pattern
        match = re.match(r"^/api/(v\d+)/", path)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _is_version_supported(version: str) -> bool:
        """
        Check if version is supported.

        Args:
            version: Version string to check

        Returns:
            True if supported, False otherwise
        """
        return version in [v.value for v in SUPPORTED_VERSIONS]

    @staticmethod
    def _is_version_deprecated(version: str) -> bool:
        """
        Check if version is deprecated.

        Currently, no versions are deprecated. This will be updated
        when newer versions are released.

        Args:
            version: Version string to check

        Returns:
            True if deprecated, False otherwise
        """
        # Currently no versions are deprecated
        return False


def setup_api_versioning(app, is_development: bool = False):
    """
    Setup API versioning middleware for FastAPI application.

    Usage:
        from fastapi import FastAPI
        from src.api.versioning import setup_api_versioning

        app = FastAPI()
        setup_api_versioning(app)

    Args:
        app: FastAPI application
        is_development: Whether running in development mode
    """
    app.add_middleware(APIVersionMiddleware)
    logger.info("API versioning middleware added")
