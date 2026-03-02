"""API Versioning Utilities and Dependencies.

This module provides utilities for API versioning, including version detection,
validation, and deprecation handling.
"""
from enum import Enum
from typing import Annotated

from fastapi import Header, HTTPException, Response, status


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
    """Extract and validate API version from request headers.

    Args:
        x_api_version: Optional API version from X-API-Version header.

    Returns:
        Validated APIVersion enum.

    Raises:
        HTTPException: If version is not supported.
    """
    if x_api_version is None:
        return APIVersion.V1

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
                "error": "INVALID_VERSION_FORMAT",
                "message": f"Invalid API version format: '{x_api_version}'",
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
    """Add deprecation headers to response.

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
    """Check if an API version is supported.

    Args:
        version: Version string to validate.

    Returns:
        True if the version is supported, False otherwise.
    """
    return version in [v.value for v in SUPPORTED_VERSIONS]


def get_successor_version(version: APIVersion) -> APIVersion | None:
    """Get the successor version for a given API version.

    Args:
        version: Current API version.

    Returns:
        Successor API version, or None if this is the latest version.
    """
    version_order = {APIVersion.V1: APIVersion.V2}
    return version_order.get(version)
