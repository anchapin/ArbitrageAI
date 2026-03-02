"""Tests for API versioning utilities and dependencies."""
import pytest
from fastapi import Response

from src.api.versioning import (
    APIVersion,
    add_deprecation_headers,
    get_api_version,
    get_successor_version,
    validate_version_supported,
)


class TestAPIVersionEnum:
    """Test APIVersion enum."""

    def test_api_version_values(self):
        """Test APIVersion enum has correct values."""
        assert APIVersion.V1.value == "v1"
        assert APIVersion.V2.value == "v2"

    def test_api_version_from_string(self):
        """Test creating APIVersion from string."""
        assert APIVersion("v1") == APIVersion.V1
        assert APIVersion("v2") == APIVersion.V2

    def test_api_version_invalid_value(self):
        """Test that invalid version raises ValueError."""
        with pytest.raises(ValueError):
            APIVersion("v3")


class TestGetAPIVersion:
    """Test get_api_version function."""

    def test_default_version(self):
        """Test that default version is v1 when no header provided."""
        version = get_api_version(None)
        assert version == APIVersion.V1

    def test_explicit_v1_version(self):
        """Test explicit v1 version from header."""
        version = get_api_version("v1")
        assert version == APIVersion.V1

    def test_explicit_v2_version(self):
        """Test explicit v2 version from header."""
        version = get_api_version("v2")
        assert version == APIVersion.V2

    def test_unsupported_version_raises_error(self):
        """Test that unsupported version raises HTTPException."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_api_version("v3")

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "VERSION_NOT_SUPPORTED"

    def test_invalid_version_format(self):
        """Test that invalid version format raises HTTPException."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_api_version("invalid")

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "INVALID_VERSION_FORMAT"


class TestValidateVersionSupported:
    """Test validate_version_supported function."""

    def test_supported_v1(self):
        """Test v1 is supported."""
        assert validate_version_supported("v1") is True

    def test_supported_v2(self):
        """Test v2 is supported."""
        assert validate_version_supported("v2") is True

    def test_unsupported_v3(self):
        """Test v3 is not supported."""
        assert validate_version_supported("v3") is False

    def test_invalid_version(self):
        """Test invalid version is not supported."""
        assert validate_version_supported("invalid") is False


class TestGetSuccessorVersion:
    """Test get_successor_version function."""

    def test_v1_successor(self):
        """Test v1 successor is v2."""
        successor = get_successor_version(APIVersion.V1)
        assert successor == APIVersion.V2

    def test_v2_no_successor(self):
        """Test v2 has no successor (latest version)."""
        successor = get_successor_version(APIVersion.V2)
        assert successor is None


class TestAddDeprecationHeaders:
    """Test add_deprecation_headers function."""

    def test_add_deprecation_header(self):
        """Test adding deprecation header."""
        response = Response()
        add_deprecation_headers(response, deprecated=True)
        assert response.headers["Deprecation"] == "true"

    def test_add_sunset_header(self):
        """Test adding sunset header."""
        response = Response()
        add_deprecation_headers(response, sunset_date="2027-06-30")
        assert response.headers["Sunset"] == "2027-06-30"

    def test_add_link_header(self):
        """Test adding link header."""
        response = Response()
        add_deprecation_headers(response, successor_version="v2")
        assert 'rel="successor-version"' in response.headers["Link"]
        assert "/api/v2" in response.headers["Link"]

    def test_add_warning_header(self):
        """Test adding warning header."""
        response = Response()
        add_deprecation_headers(
            response, warning_message="This endpoint is deprecated"
        )
        assert "299" in response.headers["Warning"]
        assert "This endpoint is deprecated" in response.headers["Warning"]

    def test_add_all_deprecation_headers(self):
        """Test adding all deprecation headers at once."""
        response = Response()
        add_deprecation_headers(
            response,
            deprecated=True,
            sunset_date="2027-06-30",
            successor_version="v2",
            warning_message="Use /api/v2 instead",
        )

        assert response.headers["Deprecation"] == "true"
        assert response.headers["Sunset"] == "2027-06-30"
        assert 'rel="successor-version"' in response.headers["Link"]
        assert "299" in response.headers["Warning"]

    def test_no_headers_when_not_deprecated(self):
        """Test that no headers are added when not deprecated."""
        response = Response()
        add_deprecation_headers(response, deprecated=False)
        assert "Deprecation" not in response.headers
        assert "Sunset" not in response.headers
        assert "Link" not in response.headers
        assert "Warning" not in response.headers
