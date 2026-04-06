"""
Tests for AppService.
"""

import pytest
from titan_plugin_appstore.clients.services.app_service import AppService
from titan_plugin_appstore.models.network import AppResponse
from titan_plugin_appstore.exceptions import ResourceNotFoundError, APIError


def test_list_apps_success(mock_api_client, sample_app_response):
    """Test successful app listing."""
    mock_api_client.get.return_value = {"data": [sample_app_response]}

    service = AppService(mock_api_client)
    apps = service.list_apps()

    assert len(apps) == 1
    assert isinstance(apps[0], AppResponse)
    assert apps[0].id == "123456789"
    assert apps[0].attributes.name == "Test App"


def test_list_apps_with_filter(mock_api_client, sample_app_response):
    """Test app listing with bundle ID filter."""
    mock_api_client.get.return_value = {"data": [sample_app_response]}

    service = AppService(mock_api_client)
    apps = service.list_apps(filter_bundle_id="com.test.app")

    mock_api_client.get.assert_called_once()
    call_args = mock_api_client.get.call_args
    assert call_args[1]["query_params"]["filter[bundleId]"] == "com.test.app"


def test_get_app_success(mock_api_client, sample_app_response):
    """Test getting specific app."""
    mock_api_client.get.return_value = {"data": sample_app_response}

    service = AppService(mock_api_client)
    app = service.get_app("123456789")

    assert isinstance(app, AppResponse)
    assert app.id == "123456789"
    mock_api_client.get.assert_called_once_with("/apps/123456789")


def test_get_app_not_found(mock_api_client):
    """Test getting non-existent app."""
    error = APIError("Not found", status_code=404)
    mock_api_client.get.side_effect = error

    service = AppService(mock_api_client)

    with pytest.raises(ResourceNotFoundError):
        service.get_app("999999999")


def test_find_app_by_bundle_id_found(mock_api_client, sample_app_response):
    """Test finding app by bundle ID - found."""
    mock_api_client.get.return_value = {"data": [sample_app_response]}

    service = AppService(mock_api_client)
    app = service.find_app_by_bundle_id("com.test.app")

    assert app is not None
    assert app.attributes.bundle_id == "com.test.app"


def test_find_app_by_bundle_id_not_found(mock_api_client):
    """Test finding app by bundle ID - not found."""
    mock_api_client.get.return_value = {"data": []}

    service = AppService(mock_api_client)
    app = service.find_app_by_bundle_id("com.nonexistent.app")

    assert app is None
