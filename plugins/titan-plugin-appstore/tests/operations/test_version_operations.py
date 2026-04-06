"""
Tests for VersionOperations.
"""

import pytest
from unittest.mock import Mock
from datetime import datetime
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_appstore.operations.version_operations import VersionOperations
from titan_plugin_appstore.models.view import VersionView
from titan_plugin_appstore.exceptions import ValidationError


@pytest.fixture
def mock_client():
    """Mock AppStoreConnectClient."""
    return Mock()


def test_suggest_next_version_current_week(mock_client):
    """Test suggesting next version using current week (YY.WW.0 format)."""
    # Mock latest version from a previous week
    latest = VersionView(
        id="123",
        version_string="26.10.0",  # Week 10 of 2026
        platform="IOS",
        state="READY_FOR_SALE",
    )
    mock_client.get_latest_version.return_value = ClientSuccess(data=latest, message="Found version")

    ops = VersionOperations(mock_client)
    next_version = ops.suggest_next_version("app123")

    # Should suggest current or next week's version in YY.WW.0 format
    now = datetime.now()
    current_year = now.year % 100
    current_week = now.isocalendar()[1]

    # Version should be YY.WW.0 format for current or next week
    parts = next_version.split(".")
    assert len(parts) == 3
    assert parts[0] == str(current_year)
    assert int(parts[1]) >= current_week  # Current week or later
    assert parts[2] == "0"


def test_suggest_next_version_same_week(mock_client):
    """Test suggesting version when latest is from current week."""
    # Mock latest version from current week
    now = datetime.now()
    current_year = now.year % 100
    current_week = now.isocalendar()[1]

    latest = VersionView(
        id="123",
        version_string=f"{current_year}.{current_week}.0",
        platform="IOS",
        state="READY_FOR_SALE",
    )
    mock_client.get_latest_version.return_value = ClientSuccess(data=latest, message="Found version")

    ops = VersionOperations(mock_client)
    next_version = ops.suggest_next_version("app123")

    # Should suggest next week's version
    parts = next_version.split(".")
    assert len(parts) == 3
    assert parts[0] == str(current_year)
    assert int(parts[1]) == current_week + 1  # Next week
    assert parts[2] == "0"


def test_suggest_next_version_year_boundary(mock_client):
    """Test suggesting version at year boundary (week 52 -> week 1)."""
    # Mock latest version from week 52 of previous year
    now = datetime.now()
    current_year = now.year % 100

    latest = VersionView(
        id="123",
        version_string=f"{current_year - 1}.52.0",  # Last week of previous year
        platform="IOS",
        state="READY_FOR_SALE",
    )
    mock_client.get_latest_version.return_value = ClientSuccess(data=latest, message="Found version")

    ops = VersionOperations(mock_client)
    next_version = ops.suggest_next_version("app123")

    # Should suggest current year and week
    parts = next_version.split(".")
    assert len(parts) == 3
    assert parts[0] == str(current_year)
    assert parts[2] == "0"


def test_suggest_next_version_no_existing(mock_client):
    """Test suggesting version when none exist (uses current week)."""
    mock_client.get_latest_version.return_value = ClientError(error_message="No versions found", error_code="NOT_FOUND")

    ops = VersionOperations(mock_client)
    next_version = ops.suggest_next_version("app123")

    # Should use current week's version YY.WW.0
    now = datetime.now()
    current_year = now.year % 100
    current_week = now.isocalendar()[1]

    expected = f"{current_year}.{current_week}.0"
    assert next_version == expected


def test_compare_versions():
    """Test version comparison."""
    ops = VersionOperations(Mock())

    assert ops.compare_versions("1.2.3", "1.2.4") == -1
    assert ops.compare_versions("1.2.3", "1.2.3") == 0
    assert ops.compare_versions("1.2.4", "1.2.3") == 1
    assert ops.compare_versions("2.0.0", "1.9.9") == 1


def test_validate_version_creation_valid(mock_client):
    """Test valid version validation."""
    mock_client.version_exists.return_value = ClientSuccess(data=False, message="Not found")

    ops = VersionOperations(mock_client)
    is_valid, error = ops.validate_version_creation("app123", "26.11.0")

    assert is_valid is True
    assert error is None


def test_validate_version_creation_invalid_format(mock_client):
    """Test invalid version format."""
    ops = VersionOperations(mock_client)

    is_valid, error = ops.validate_version_creation("app123", "1")
    assert is_valid is False
    assert "2-4 parts" in error

    is_valid, error = ops.validate_version_creation("app123", "1.2.3.4.5")
    assert is_valid is False
    assert "2-4 parts" in error


def test_validate_version_creation_conflict(mock_client):
    """Test version conflict validation."""
    mock_client.version_exists.return_value = ClientSuccess(data=True, message="Version exists")

    ops = VersionOperations(mock_client)
    is_valid, error = ops.validate_version_creation("app123", "26.11.0")

    assert is_valid is False
    assert "already exists" in error
