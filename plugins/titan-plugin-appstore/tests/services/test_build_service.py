"""
Tests for BuildService.

These tests use mocked API responses to verify service logic.
"""

import pytest
from unittest.mock import MagicMock, patch

from titan_plugin_appstore.clients.services.build_service import BuildService
from titan_plugin_appstore.models.network import BuildResponse, BuildAttributes
from titan_plugin_appstore.exceptions import APIError


# ==================== Fixtures ====================


@pytest.fixture
def mock_api():
    """Mock API client."""
    return MagicMock()


@pytest.fixture
def build_service(mock_api):
    """Build service with mocked API."""
    return BuildService(mock_api)


@pytest.fixture
def sample_build_data():
    """Sample build API response data."""
    return {
        "type": "builds",
        "id": "build123",
        "attributes": {
            "version": "1.2.3",
            "uploadedDate": "2024-01-15T10:00:00Z",
            "expiresDate": None,
            "expired": False,
            "minOsVersion": "15.0",
            "processingState": "VALID",
            "usesNonExemptEncryption": False,
        },
        "relationships": {},
        "links": {},
    }


# ==================== list_builds ====================


def test_list_builds_success(build_service, mock_api, sample_build_data):
    """Test listing builds successfully."""
    # Mock API response
    mock_api.get.return_value = {
        "data": [sample_build_data, sample_build_data],
        "links": {},
        "meta": {},
    }

    # Call service
    builds = build_service.list_builds(app_id="app123")

    # Verify API call
    mock_api.get.assert_called_once()
    call_args = mock_api.get.call_args
    assert call_args[0][0] == "/builds"

    query_params = call_args[1]["query_params"]
    assert query_params["filter[app]"] == "app123"
    assert query_params["filter[expired]"] == "false"
    assert query_params["filter[processingState]"] == "VALID"
    assert query_params["sort"] == "-uploadedDate"

    # Verify result
    assert len(builds) == 2
    assert all(isinstance(b, BuildResponse) for b in builds)
    assert builds[0].id == "build123"
    assert builds[0].attributes.version == "1.2.3"


def test_list_builds_with_version_filter(build_service, mock_api, sample_build_data):
    """Test listing builds with version filter."""
    mock_api.get.return_value = {
        "data": [sample_build_data],
        "links": {},
        "meta": {},
    }

    builds = build_service.list_builds(app_id="app123", version_id="version456")

    # Verify API call includes version filter
    call_args = mock_api.get.call_args
    query_params = call_args[1]["query_params"]
    assert query_params["filter[appStoreVersion]"] == "version456"


def test_list_builds_empty(build_service, mock_api):
    """Test listing builds when none available."""
    mock_api.get.return_value = {
        "data": [],
        "links": {},
        "meta": {},
    }

    builds = build_service.list_builds(app_id="app123")

    assert builds == []


def test_list_builds_validation_error(build_service, mock_api):
    """Test handling of malformed API response."""
    # Return invalid data that will fail Pydantic validation
    mock_api.get.return_value = {
        "data": [{"invalid": "data"}],
    }

    with pytest.raises(APIError) as exc_info:
        build_service.list_builds(app_id="app123")

    assert "Failed to parse build data" in str(exc_info.value)


# ==================== get_build ====================


def test_get_build_success(build_service, mock_api, sample_build_data):
    """Test getting a specific build."""
    mock_api.get.return_value = {
        "data": sample_build_data,
    }

    build = build_service.get_build(build_id="build123")

    # Verify API call
    mock_api.get.assert_called_once_with("/builds/build123")

    # Verify result
    assert isinstance(build, BuildResponse)
    assert build.id == "build123"
    assert build.attributes.version == "1.2.3"
    assert build.attributes.processing_state == "VALID"


def test_get_build_not_found(build_service, mock_api):
    """Test getting a build that doesn't exist."""
    from titan_plugin_appstore.exceptions import ResourceNotFoundError

    mock_api.get.return_value = {
        "data": None,
    }

    with pytest.raises(ResourceNotFoundError) as exc_info:
        build_service.get_build(build_id="build123")

    assert "Build build123 not found" in str(exc_info.value)


def test_get_build_validation_error(build_service, mock_api):
    """Test handling of malformed build data."""
    mock_api.get.return_value = {
        "data": {"invalid": "data"},
    }

    with pytest.raises(APIError) as exc_info:
        build_service.get_build(build_id="build123")

    assert "Failed to parse build data" in str(exc_info.value)
