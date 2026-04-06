"""
Tests for VersionService.
"""

import pytest
from titan_plugin_appstore.clients.services.version_service import VersionService
from titan_plugin_appstore.models.network import AppStoreVersionResponse
from titan_plugin_appstore.exceptions import (
    ResourceNotFoundError,
    VersionConflictError,
    APIError,
)


def test_list_versions_success(mock_api_client, sample_version_response):
    """Test successful version listing."""
    mock_api_client.get.return_value = {"data": [sample_version_response]}

    service = VersionService(mock_api_client)
    versions = service.list_versions("123456789")

    assert len(versions) == 1
    assert isinstance(versions[0], AppStoreVersionResponse)
    assert versions[0].attributes.version_string == "1.2.3"


def test_list_versions_with_filters(mock_api_client, sample_version_response):
    """Test version listing with filters."""
    mock_api_client.get.return_value = {"data": [sample_version_response]}

    service = VersionService(mock_api_client)
    versions = service.list_versions("123456789", platform="IOS", version_string="1.2.3")

    call_args = mock_api_client.get.call_args
    query_params = call_args[1]["query_params"]
    assert query_params["filter[platform]"] == "IOS"
    assert query_params["filter[versionString]"] == "1.2.3"


def test_create_version_success(mock_api_client, sample_version_response):
    """Test successful version creation."""
    mock_api_client.get.return_value = {"data": []}  # No existing versions
    mock_api_client.post.return_value = {"data": sample_version_response}

    service = VersionService(mock_api_client)
    version = service.create_version(
        app_id="123456789", version_string="1.2.3", platform="IOS"
    )

    assert isinstance(version, AppStoreVersionResponse)
    assert version.attributes.version_string == "1.2.3"


def test_create_version_conflict(mock_api_client, sample_version_response):
    """Test version creation with conflict."""
    # Existing version found
    mock_api_client.get.return_value = {"data": [sample_version_response]}

    service = VersionService(mock_api_client)

    with pytest.raises(VersionConflictError):
        service.create_version(app_id="123456789", version_string="1.2.3")


def test_version_exists_true(mock_api_client, sample_version_response):
    """Test version_exists returns True."""
    mock_api_client.get.return_value = {"data": [sample_version_response]}

    service = VersionService(mock_api_client)
    exists = service.version_exists("123456789", "1.2.3")

    assert exists is True


def test_version_exists_false(mock_api_client):
    """Test version_exists returns False."""
    mock_api_client.get.return_value = {"data": []}

    service = VersionService(mock_api_client)
    exists = service.version_exists("123456789", "1.2.4")

    assert exists is False


def test_delete_version_success(mock_api_client):
    """Test successful version deletion."""
    mock_api_client.delete.return_value = None

    service = VersionService(mock_api_client)
    service.delete_version("987654321")

    mock_api_client.delete.assert_called_once_with("/appStoreVersions/987654321")


def test_delete_version_not_found(mock_api_client):
    """Test deleting non-existent version."""
    error = APIError("Not found", status_code=404)
    mock_api_client.delete.side_effect = error

    service = VersionService(mock_api_client)

    with pytest.raises(ResourceNotFoundError):
        service.delete_version("999999999")
