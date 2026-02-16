"""
Unit tests for IssueService

Tests the Service layer which transforms Network models to UI models
and wraps results in ClientResult.
"""

import pytest
import json
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_github.clients.services import IssueService
from titan_plugin_github.exceptions import GitHubAPIError


@pytest.fixture
def issue_service(mock_gh_network):
    """Create an IssueService instance"""
    return IssueService(mock_gh_network)


@pytest.fixture
def sample_issue_json():
    """Sample issue response from gh CLI"""
    return {
        "number": 456,
        "title": "bug: Fix login issue",
        "body": "Users cannot login",
        "state": "open",
        "author": {
            "login": "test-user",
            "name": "Test User",
            "email": "test@example.com"
        },
        "labels": [{"name": "bug"}, {"name": "high-priority"}],
        "createdAt": "2025-01-15T10:00:00Z",
        "updatedAt": "2025-01-15T11:00:00Z"
    }


def test_create_issue_success(issue_service, mock_gh_network, sample_issue_json):
    """Test successful issue creation"""
    # Setup mock - create returns URL, view returns issue data
    issue_url = "https://github.com/test-owner/test-repo/issues/456"
    mock_gh_network.run_command.side_effect = [
        issue_url,  # issue create
        json.dumps(sample_issue_json)  # issue view
    ]

    # Call service
    result = issue_service.create_issue(
        title="bug: Fix login issue",
        body="Users cannot login",
        assignees=["test-user"],
        labels=["bug"]
    )

    # Assertions
    assert isinstance(result, ClientSuccess)
    assert result.data.number == 456
    assert result.data.title == "bug: Fix login issue"
    assert result.data.body == "Users cannot login"
    assert "bug" in result.data.labels

    # Verify network calls
    create_call_args = mock_gh_network.run_command.call_args_list[0][0][0]
    assert "issue" in create_call_args
    assert "create" in create_call_args
    assert "--title" in create_call_args
    assert "--body" in create_call_args


def test_create_issue_with_multiple_assignees(issue_service, mock_gh_network, sample_issue_json):
    """Test creating issue with multiple assignees"""
    issue_url = "https://github.com/test-owner/test-repo/issues/456"
    mock_gh_network.run_command.side_effect = [
        issue_url,
        json.dumps(sample_issue_json)
    ]

    result = issue_service.create_issue(
        title="Test Issue",
        body="Description",
        assignees=["user1", "user2", "user3"]
    )

    assert isinstance(result, ClientSuccess)

    # Verify multiple assignees were passed
    create_call_args = mock_gh_network.run_command.call_args_list[0][0][0]
    assert "--assignee" in create_call_args


def test_create_issue_with_labels(issue_service, mock_gh_network, sample_issue_json):
    """Test creating issue with labels"""
    issue_url = "https://github.com/test-owner/test-repo/issues/456"
    mock_gh_network.run_command.side_effect = [
        issue_url,
        json.dumps(sample_issue_json)
    ]

    result = issue_service.create_issue(
        title="Test Issue",
        body="Description",
        labels=["bug", "enhancement"]
    )

    assert isinstance(result, ClientSuccess)

    # Verify labels were passed
    create_call_args = mock_gh_network.run_command.call_args_list[0][0][0]
    assert "--label" in create_call_args


def test_create_issue_api_error(issue_service, mock_gh_network):
    """Test issue creation when API returns error"""
    # Setup mock to raise API error
    mock_gh_network.run_command.side_effect = GitHubAPIError("Repository not found")

    result = issue_service.create_issue(
        title="Test Issue",
        body="Description"
    )

    assert isinstance(result, ClientError)
    assert "repository" in result.error_message.lower()


def test_create_issue_parse_error(issue_service, mock_gh_network):
    """Test issue creation with invalid URL response"""
    # Setup mock to return invalid URL (can't extract number)
    mock_gh_network.run_command.side_effect = [
        "invalid-url-without-number",
        "{}"
    ]

    result = issue_service.create_issue(
        title="Test Issue",
        body="Description"
    )

    assert isinstance(result, ClientError)
    assert result.error_code == "PARSE_ERROR"


def test_list_labels_success(issue_service, mock_gh_network):
    """Test successful label listing"""
    # Setup mock
    labels_json = [
        {"name": "bug"},
        {"name": "feature"},
        {"name": "enhancement"}
    ]
    mock_gh_network.run_command.return_value = json.dumps(labels_json)

    result = issue_service.list_labels()

    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 3
    assert "bug" in result.data
    assert "feature" in result.data
    assert "enhancement" in result.data

    # Verify network call
    call_args = mock_gh_network.run_command.call_args[0][0]
    assert "label" in call_args
    assert "list" in call_args


def test_list_labels_empty(issue_service, mock_gh_network):
    """Test listing labels when none exist"""
    # Setup mock to return empty array
    mock_gh_network.run_command.return_value = "[]"

    result = issue_service.list_labels()

    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 0
    assert "0 labels" in result.message


def test_list_labels_invalid_json(issue_service, mock_gh_network):
    """Test listing labels with invalid JSON response"""
    # Setup mock to return invalid JSON
    mock_gh_network.run_command.return_value = "invalid json ["

    result = issue_service.list_labels()

    assert isinstance(result, ClientError)
    assert result.error_code == "JSON_PARSE_ERROR"


def test_list_labels_api_error(issue_service, mock_gh_network):
    """Test listing labels when API fails"""
    # Setup mock to raise API error
    mock_gh_network.run_command.side_effect = GitHubAPIError("Authentication required")

    result = issue_service.list_labels()

    assert isinstance(result, ClientError)
    assert result.error_code == "API_ERROR"
