"""
Unit tests for PRService

Tests the Service layer which transforms Network models to UI models
and wraps results in ClientResult.
"""

import pytest
import json
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_github.clients.services import PRService
from titan_plugin_github.exceptions import GitHubAPIError


@pytest.fixture
def pr_service(mock_gh_network):
    """Create a PRService instance"""
    return PRService(mock_gh_network)


@pytest.fixture
def sample_pr_json():
    """Sample PR response from gh CLI"""
    return {
        "number": 123,
        "title": "feat: Add new feature",
        "body": "This PR adds a new feature",
        "state": "OPEN",
        "author": {
            "login": "test-user",
            "name": "Test User",
            "email": "test@example.com"
        },
        "baseRefName": "main",
        "headRefName": "feat/new-feature",
        "additions": 50,
        "deletions": 10,
        "changedFiles": 3,
        "mergeable": "MERGEABLE",
        "isDraft": False,
        "createdAt": "2025-01-15T10:00:00Z",
        "updatedAt": "2025-01-15T11:00:00Z",
        "mergedAt": None,
        "reviews": [],
        "labels": [{"name": "feature"}, {"name": "backend"}]
    }


def test_get_pull_request_success(pr_service, mock_gh_network, sample_pr_json):
    """Test successful PR retrieval"""
    # Setup mock
    mock_gh_network.run_command.return_value = json.dumps(sample_pr_json)

    # Call service
    result = pr_service.get_pull_request(123)

    # Assertions
    assert isinstance(result, ClientSuccess)
    assert result.data.number == 123
    assert result.data.title == "feat: Add new feature"
    assert result.data.state == "OPEN"
    assert result.data.author_name == "test-user"
    assert result.data.head_ref == "feat/new-feature"
    assert result.data.base_ref == "main"
    assert result.data.stats == "+50 -10"
    assert result.data.is_mergeable is True
    assert result.data.is_draft is False
    assert "feature" in result.data.labels
    assert "backend" in result.data.labels

    # Verify network was called correctly
    call_args = mock_gh_network.run_command.call_args[0][0]
    assert "pr" in call_args
    assert "view" in call_args
    assert "123" in call_args


def test_get_pull_request_draft(pr_service, mock_gh_network, sample_pr_json):
    """Test retrieving draft PR"""
    # Make it a draft
    sample_pr_json["isDraft"] = True
    mock_gh_network.run_command.return_value = json.dumps(sample_pr_json)

    result = pr_service.get_pull_request(123)

    assert isinstance(result, ClientSuccess)
    assert result.data.is_draft is True
    assert result.data.status_icon == "📝"  # Draft icon


def test_get_pull_request_merged(pr_service, mock_gh_network, sample_pr_json):
    """Test retrieving merged PR"""
    # Make it merged
    sample_pr_json["state"] = "MERGED"
    sample_pr_json["mergedAt"] = "2025-01-15T12:00:00Z"
    mock_gh_network.run_command.return_value = json.dumps(sample_pr_json)

    result = pr_service.get_pull_request(123)

    assert isinstance(result, ClientSuccess)
    assert result.data.state == "MERGED"
    assert result.data.status_icon == "🟣"  # Merged icon


def test_get_pull_request_not_found(pr_service, mock_gh_network):
    """Test PR retrieval when PR doesn't exist"""
    # Setup mock to raise API error
    mock_gh_network.run_command.side_effect = GitHubAPIError("pull request not found")

    # Call service
    result = pr_service.get_pull_request(999)

    # Assertions
    assert isinstance(result, ClientError)
    assert "not found" in result.error_message.lower()


def test_get_pull_request_invalid_json(pr_service, mock_gh_network):
    """Test PR retrieval with invalid JSON response"""
    # Setup mock to return invalid JSON
    mock_gh_network.run_command.return_value = "invalid json {"

    # Call service
    result = pr_service.get_pull_request(123)

    # Assertions
    assert isinstance(result, ClientError)
    assert result.error_code == "JSON_PARSE_ERROR"


def test_merge_pr_success(pr_service, mock_gh_network):
    """Test successful PR merge"""
    # Setup mock - merge command returns output with SHA
    mock_gh_network.run_command.return_value = "✓ Merged pull request #123 (abc123d)"

    result = pr_service.merge_pr(123, merge_method="squash")

    assert isinstance(result, ClientSuccess)
    assert result.data.merged is True
    assert result.data.status_icon == "✅"
    assert result.data.sha_short == "abc123d"

    # Verify args
    call_args = mock_gh_network.run_command.call_args[0][0]
    assert "pr" in call_args
    assert "merge" in call_args
    assert "123" in call_args
    assert "--squash" in call_args


def test_merge_pr_invalid_method(pr_service, mock_gh_network):
    """Test merge with invalid merge method"""
    result = pr_service.merge_pr(123, merge_method="invalid-method")

    assert isinstance(result, ClientSuccess)
    assert result.data.merged is False
    assert result.data.status_icon == "❌"
    assert "invalid" in result.data.message.lower()


def test_merge_pr_failure(pr_service, mock_gh_network):
    """Test PR merge failure"""
    # Setup mock to raise API error
    mock_gh_network.run_command.side_effect = GitHubAPIError("PR not mergeable")

    result = pr_service.merge_pr(123)

    assert isinstance(result, ClientSuccess)
    assert result.data.merged is False
    assert result.data.status_icon == "❌"
    assert "not mergeable" in result.data.message.lower()
