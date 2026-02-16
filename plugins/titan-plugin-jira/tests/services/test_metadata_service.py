"""
Unit tests for MetadataService

Tests metadata operations: issue types, statuses, versions, current user.
"""

import pytest
from unittest.mock import Mock
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_jira.clients.services import MetadataService
from titan_plugin_jira.exceptions import JiraAPIError


@pytest.fixture
def mock_network():
    """Create a mock JiraNetwork"""
    return Mock()


@pytest.fixture
def metadata_service(mock_network):
    """Create a MetadataService instance"""
    return MetadataService(mock_network)


@pytest.fixture
def sample_project_response():
    """Sample project response with issue types"""
    return {
        "id": "10000",
        "key": "TEST",
        "name": "Test Project",
        "issueTypes": [
            {
                "id": "10004",
                "name": "Bug",
                "description": "A software bug",
                "subtask": False,
                "iconUrl": "https://test.atlassian.net/images/icons/bug.png"
            },
            {
                "id": "10001",
                "name": "Story",
                "description": "A user story",
                "subtask": False,
                "iconUrl": "https://test.atlassian.net/images/icons/story.png"
            },
            {
                "id": "10005",
                "name": "Sub-task",
                "description": "A sub-task",
                "subtask": True,
                "iconUrl": "https://test.atlassian.net/images/icons/subtask.png"
            }
        ]
    }


def test_get_issue_types_success(metadata_service, mock_network, sample_project_response):
    """Test successful retrieval of issue types"""
    # Setup mock
    mock_network.make_request.return_value = sample_project_response

    # Call service
    result = metadata_service.get_issue_types("TEST")

    # Assertions
    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 3
    assert result.data[0].id == "10004"
    assert result.data[0].name == "Bug"
    assert result.data[0].subtask is False
    assert result.data[2].name == "Sub-task"
    assert result.data[2].subtask is True
    assert "Found 3 issue types" in result.message

    # Verify network call
    mock_network.make_request.assert_called_once_with("GET", "project/TEST")


def test_get_issue_types_api_error(metadata_service, mock_network):
    """Test get_issue_types when API returns error"""
    # Setup mock to raise error
    mock_network.make_request.side_effect = JiraAPIError("Project not found", status_code=404)

    # Call service
    result = metadata_service.get_issue_types("NOTFOUND")

    # Assertions
    assert isinstance(result, ClientError)
    assert result.error_code == "GET_ISSUE_TYPES_ERROR"


@pytest.fixture
def sample_statuses_response():
    """Sample statuses response"""
    return [
        {
            "name": "Bug",
            "statuses": [
                {
                    "id": "1",
                    "name": "To Do",
                    "description": "Task is ready to be worked on",
                    "statusCategory": {
                        "name": "To Do",
                        "key": "new"
                    }
                },
                {
                    "id": "3",
                    "name": "In Progress",
                    "description": "Work in progress",
                    "statusCategory": {
                        "name": "In Progress",
                        "key": "indeterminate"
                    }
                }
            ]
        },
        {
            "name": "Story",
            "statuses": [
                {
                    "id": "1",
                    "name": "To Do",
                    "description": "Task is ready to be worked on",
                    "statusCategory": {
                        "name": "To Do",
                        "key": "new"
                    }
                },
                {
                    "id": "10",
                    "name": "Done",
                    "description": "Work completed",
                    "statusCategory": {
                        "name": "Done",
                        "key": "done"
                    }
                }
            ]
        }
    ]


def test_list_statuses_success(metadata_service, mock_network, sample_statuses_response):
    """Test successful retrieval of statuses"""
    # Setup mock
    mock_network.make_request.return_value = sample_statuses_response

    # Call service
    result = metadata_service.list_statuses("TEST")

    # Assertions
    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 3  # To Do, In Progress, Done (unique)

    # Verify statuses are deduplicated
    status_names = [s["name"] for s in result.data]
    assert "To Do" in status_names
    assert "In Progress" in status_names
    assert "Done" in status_names
    assert status_names.count("To Do") == 1  # Should appear only once

    # Verify structure
    assert result.data[0]["id"] is not None
    assert result.data[0]["name"] is not None
    assert result.data[0]["category"] is not None

    # Verify network call
    mock_network.make_request.assert_called_once_with("GET", "project/TEST/statuses")


def test_list_statuses_api_error(metadata_service, mock_network):
    """Test list_statuses when API returns error"""
    # Setup mock to raise error
    mock_network.make_request.side_effect = JiraAPIError("Forbidden", status_code=403)

    # Call service
    result = metadata_service.list_statuses("TEST")

    # Assertions
    assert isinstance(result, ClientError)
    assert result.error_code == "LIST_STATUSES_ERROR"


def test_get_current_user_success(metadata_service, mock_network):
    """Test successful retrieval of current user"""
    # Setup mock
    user_data = {
        "accountId": "557058:f58131cb-b67d-43c7-b30d-6b58d40bd077",
        "displayName": "John Doe",
        "emailAddress": "john.doe@example.com",
        "active": True
    }
    mock_network.make_request.return_value = user_data

    # Call service
    result = metadata_service.get_current_user()

    # Assertions
    assert isinstance(result, ClientSuccess)
    assert result.data["displayName"] == "John Doe"
    assert result.data["emailAddress"] == "john.doe@example.com"
    assert "Current user retrieved" in result.message

    # Verify network call
    mock_network.make_request.assert_called_once_with("GET", "myself")


def test_get_current_user_api_error(metadata_service, mock_network):
    """Test get_current_user when API returns error"""
    # Setup mock to raise error
    mock_network.make_request.side_effect = JiraAPIError("Unauthorized", status_code=401)

    # Call service
    result = metadata_service.get_current_user()

    # Assertions
    assert isinstance(result, ClientError)
    assert result.error_code == "GET_USER_ERROR"


@pytest.fixture
def sample_project_with_versions():
    """Sample project response with versions"""
    return {
        "id": "10000",
        "key": "TEST",
        "name": "Test Project",
        "versions": [
            {
                "id": "10200",
                "name": "v1.0.0",
                "description": "First release",
                "released": True,
                "releaseDate": "2025-01-01"
            },
            {
                "id": "10201",
                "name": "v1.1.0",
                "description": "Bug fixes",
                "released": False,
                "releaseDate": None
            },
            {
                "id": "10202",
                "name": "v2.0.0",
                "description": "Major release",
                "released": False,
                "releaseDate": "2025-06-01"
            }
        ]
    }


def test_list_project_versions_success(metadata_service, mock_network, sample_project_with_versions):
    """Test successful retrieval of project versions"""
    # Setup mock
    mock_network.make_request.return_value = sample_project_with_versions

    # Call service
    result = metadata_service.list_project_versions("TEST")

    # Assertions
    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 3

    # Verify version structure
    v1 = result.data[0]
    assert v1["id"] == "10200"
    assert v1["name"] == "v1.0.0"
    assert v1["description"] == "First release"
    assert v1["released"] is True
    assert v1["releaseDate"] == "2025-01-01"

    v2 = result.data[1]
    assert v2["released"] is False
    assert v2["releaseDate"] is None

    assert "Found 3 versions" in result.message

    # Verify network call
    mock_network.make_request.assert_called_once_with("GET", "project/TEST")


def test_list_project_versions_no_versions(metadata_service, mock_network):
    """Test list_project_versions when project has no versions"""
    # Setup mock
    mock_network.make_request.return_value = {
        "id": "10000",
        "key": "TEST",
        "name": "Test Project",
        "versions": []
    }

    # Call service
    result = metadata_service.list_project_versions("TEST")

    # Assertions
    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 0
    assert "Found 0 versions" in result.message


def test_list_project_versions_api_error(metadata_service, mock_network):
    """Test list_project_versions when API returns error"""
    # Setup mock to raise error
    mock_network.make_request.side_effect = JiraAPIError("Project not found", status_code=404)

    # Call service
    result = metadata_service.list_project_versions("NOTFOUND")

    # Assertions
    assert isinstance(result, ClientError)
    assert result.error_code == "LIST_VERSIONS_ERROR"
