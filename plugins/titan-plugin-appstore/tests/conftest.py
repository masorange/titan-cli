"""
Pytest fixtures for App Store Connect plugin tests.
"""

import pytest
from unittest.mock import Mock, MagicMock


@pytest.fixture
def mock_api_client():
    """Mock AppStoreConnectAPI client."""
    client = Mock()
    client.get = MagicMock()
    client.post = MagicMock()
    client.patch = MagicMock()
    client.delete = MagicMock()
    return client


@pytest.fixture
def sample_app_response():
    """Sample app response from API."""
    return {
        "type": "apps",
        "id": "123456789",
        "attributes": {
            "name": "Test App",
            "bundleId": "com.test.app",
            "sku": "TEST-SKU-001",
            "primaryLocale": "en-US",
        },
    }


@pytest.fixture
def sample_version_response():
    """Sample version response from API."""
    return {
        "type": "appStoreVersions",
        "id": "987654321",
        "attributes": {
            "versionString": "1.2.3",
            "platform": "IOS",
            "appStoreState": "PREPARE_FOR_SUBMISSION",
            "releaseType": "MANUAL",
            "createdDate": "2026-03-09T10:00:00.000+0000",
        },
    }
