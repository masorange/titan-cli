"""
Pytest configuration and shared fixtures for GitHub plugin tests
"""

import pytest
from unittest.mock import Mock
from titan_plugin_github.models.network.graphql import GraphQLPullRequestReviewThread, GraphQLPullRequestReviewComment, GraphQLUser


@pytest.fixture
def mock_github_client():
    """Create a mock GitHub client for testing"""
    client = Mock()
    client.repo_owner = "test-owner"
    client.repo_name = "test-repo"

    # Mock common methods
    client.reply_to_comment = Mock(return_value=True)
    client.resolve_review_thread = Mock(return_value=True)
    client.request_pr_review = Mock(return_value=True)

    return client


@pytest.fixture
def mock_git_client():
    """Create a mock Git client for testing"""
    client = Mock()
    client.main_branch = "main"

    # Mock git commands
    client.run_in_worktree = Mock(return_value="")
    client.create_worktree = Mock(return_value=True)
    client.remove_worktree = Mock(return_value=True)

    return client


@pytest.fixture
def mock_ai_client():
    """Create a mock AI client for testing"""
    client = Mock()
    client.is_available = Mock(return_value=True)
    client.execute = Mock(return_value="AI response")
    return client


@pytest.fixture
def sample_github_user():
    """Create a sample GitHub user"""
    return GraphQLUser(
        login="test-user",
        name="Test User"
    )


@pytest.fixture
def sample_review_comment(sample_github_user):
    """Create a sample review comment"""
    return GraphQLPullRequestReviewComment(
        databaseId=1001,
        body="This needs to be fixed",
        author=sample_github_user,
        createdAt="2025-01-15T10:00:00Z",
        updatedAt="2025-01-15T10:00:00Z",
        path="src/main.py",
        line=42,
        diffHunk="@@ -40,7 +40,7 @@\n def main():\n-    old_code()\n+    new_code()\n"
    )


@pytest.fixture
def sample_pr_thread(sample_review_comment, sample_github_user):
    """Create a sample PR review thread"""
    reply = GraphQLPullRequestReviewComment(
        databaseId=1002,
        body="I'll fix this",
        author=sample_github_user,
        createdAt="2025-01-15T11:00:00Z",
        updatedAt="2025-01-15T11:00:00Z",
        path="src/main.py",
        line=42,
        diffHunk=None
    )

    return GraphQLPullRequestReviewThread(
        id="thread_123",
        isResolved=False,
        isOutdated=False,
        path="src/main.py",
        comments=[sample_review_comment, reply]
    )


@pytest.fixture
def sample_pr_threads(sample_pr_thread):
    """Create a list of sample PR threads"""
    return [sample_pr_thread]


@pytest.fixture
def sample_ui_comment_thread(sample_pr_thread):
    """Create a sample UI comment thread (view model)"""
    from titan_plugin_github.models.view import UICommentThread
    return UICommentThread.from_review_thread(sample_pr_thread)


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers",
        "unit: marks tests as unit tests (use mocks, no external dependencies)"
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (require real APIs)"
    )
