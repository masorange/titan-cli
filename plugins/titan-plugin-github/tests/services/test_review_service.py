"""
Unit tests for ReviewService

Tests the Service layer which transforms Network models to UI models
and wraps results in ClientResult.
"""

import pytest
import json
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_github.clients.services import ReviewService
from titan_plugin_github.exceptions import GitHubAPIError


@pytest.fixture
def review_service(mock_gh_network, mock_graphql_network):
    """Create a ReviewService instance"""
    return ReviewService(mock_gh_network, mock_graphql_network)


@pytest.fixture
def sample_review_json():
    """Sample review response from GitHub API"""
    return {
        "id": 123,
        "user": {
            "login": "test-user",
            "name": "Test User",
            "email": "test@example.com"
        },
        "body": "Looks good to me!",
        "state": "APPROVED",
        "submitted_at": "2025-01-15T10:00:00Z",
        "commit_id": "abc123def456789"
    }


@pytest.fixture
def sample_thread_graphql_response():
    """Sample GraphQL response for review threads"""
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "nodes": [
                            {
                                "id": "thread_123",
                                "isResolved": False,
                                "isOutdated": False,
                                "path": "src/main.py",
                                "comments": {
                                    "nodes": [
                                        {
                                            "databaseId": 1001,
                                            "body": "This needs to be fixed",
                                            "author": {
                                                "login": "reviewer",
                                                "name": "Reviewer Name"
                                            },
                                            "createdAt": "2025-01-15T10:00:00Z",
                                            "updatedAt": "2025-01-15T10:00:00Z",
                                            "path": "src/main.py",
                                            "line": 42,
                                            "originalLine": None,
                                            "diffHunk": "@@ -40,7 +40,7 @@"
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }


def test_get_pr_reviews_success(review_service, mock_gh_network, sample_review_json):
    """Test successful retrieval of PR reviews"""
    # Setup mock
    reviews_json = [sample_review_json]
    mock_gh_network.run_command.return_value = json.dumps(reviews_json)

    # Call service
    result = review_service.get_pr_reviews(123)

    # Assertions
    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 1
    assert result.data[0].id == 123
    assert result.data[0].author_name == "Test User"
    assert result.data[0].state == "APPROVED"
    assert result.data[0].state_icon == "🟢"
    assert result.data[0].commit_id_short == "abc123d"

    # Verify network call
    call_args = mock_gh_network.run_command.call_args[0][0]
    assert "api" in call_args
    assert "/pulls/123/reviews" in " ".join(call_args)


def test_get_pr_reviews_multiple(review_service, mock_gh_network, sample_review_json):
    """Test retrieving multiple reviews"""
    # Setup mock with multiple reviews
    reviews_json = [
        sample_review_json,
        {
            "id": 124,
            "user": {"login": "user2", "name": "User Two"},
            "body": "Needs changes",
            "state": "CHANGES_REQUESTED",
            "submitted_at": "2025-01-15T11:00:00Z",
            "commit_id": "def456abc123"
        }
    ]
    mock_gh_network.run_command.return_value = json.dumps(reviews_json)

    result = review_service.get_pr_reviews(123)

    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 2
    assert result.data[0].state_icon == "🟢"  # APPROVED
    assert result.data[1].state_icon == "🔴"  # CHANGES_REQUESTED


def test_get_pr_reviews_empty(review_service, mock_gh_network):
    """Test getting reviews when none exist"""
    # Setup mock to return empty array
    mock_gh_network.run_command.return_value = "[]"

    result = review_service.get_pr_reviews(123)

    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 0
    assert "0 reviews" in result.message


def test_get_pr_reviews_api_error(review_service, mock_gh_network):
    """Test getting reviews when API fails"""
    # Setup mock to raise API error
    mock_gh_network.run_command.side_effect = GitHubAPIError("PR not found")

    result = review_service.get_pr_reviews(999)

    assert isinstance(result, ClientError)
    assert result.error_code == "API_ERROR"


def test_get_pr_review_threads_success(review_service, mock_graphql_network, sample_thread_graphql_response):
    """Test successful retrieval of review threads"""
    # Setup mock
    mock_graphql_network.run_query.return_value = sample_thread_graphql_response

    # Call service
    result = review_service.get_pr_review_threads(123)

    # Assertions
    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 1
    assert result.data[0].thread_id == "thread_123"
    assert result.data[0].is_resolved is False
    assert result.data[0].main_comment.body == "This needs to be fixed"

    # Verify GraphQL query was called
    assert mock_graphql_network.run_query.called


def test_get_pr_review_threads_filter_resolved(review_service, mock_graphql_network):
    """Test filtering out resolved threads"""
    # Setup mock with resolved and unresolved threads
    response = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "nodes": [
                            {
                                "id": "thread_1",
                                "isResolved": True,
                                "isOutdated": False,
                                "path": "src/a.py",
                                "comments": {"nodes": []}
                            },
                            {
                                "id": "thread_2",
                                "isResolved": False,
                                "isOutdated": False,
                                "path": "src/b.py",
                                "comments": {"nodes": []}
                            }
                        ]
                    }
                }
            }
        }
    }
    mock_graphql_network.run_query.return_value = response

    # Call with include_resolved=False
    result = review_service.get_pr_review_threads(123, include_resolved=False)

    # Should only return unresolved thread
    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 1
    assert result.data[0].thread_id == "thread_2"


def test_get_pr_review_threads_empty(review_service, mock_graphql_network):
    """Test getting threads when none exist"""
    # Setup mock with empty threads
    response = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "nodes": []
                    }
                }
            }
        }
    }
    mock_graphql_network.run_query.return_value = response

    result = review_service.get_pr_review_threads(123)

    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 0


def test_resolve_review_thread_success(review_service, mock_graphql_network):
    """Test successful thread resolution"""
    # Setup mock
    mock_graphql_network.run_mutation.return_value = {"data": {}}

    result = review_service.resolve_review_thread("thread_123")

    assert isinstance(result, ClientSuccess)
    assert result.message == "Review thread resolved"

    # Verify mutation was called
    assert mock_graphql_network.run_mutation.called


def test_resolve_review_thread_api_error(review_service, mock_graphql_network):
    """Test resolving thread when API fails"""
    # Setup mock to raise API error
    mock_graphql_network.run_mutation.side_effect = GitHubAPIError("Thread not found")

    result = review_service.resolve_review_thread("invalid_thread")

    assert isinstance(result, ClientError)
    assert result.error_code == "API_ERROR"
