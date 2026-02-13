"""
Unit tests for PR operations
"""

import pytest
from titan_plugin_github.operations.pr_operations import (
    fetch_pr_threads,
    push_and_request_review,
)
from titan_plugin_github.models import PRReviewThread, PRReviewComment, User


@pytest.mark.unit
class TestFetchPRThreads:
    """Test fetching and filtering PR threads"""

    def test_filters_bot_comments(self, mock_github_client):
        """Test that bot comments are filtered out"""
        bot_user = User(login="dependabot[bot]", avatar_url="")
        human_user = User(login="reviewer", avatar_url="")

        bot_comment = PRReviewComment(
            id=1, body="Bot message", author=bot_user,
            created_at="2025-01-01", updated_at="2025-01-01",
            path="file.py", line=1, diff_hunk=""
        )
        human_comment = PRReviewComment(
            id=2, body="Real review", author=human_user,
            created_at="2025-01-01", updated_at="2025-01-01",
            path="file.py", line=2, diff_hunk=""
        )

        threads = [
            PRReviewThread(id="t1", is_resolved=False, is_outdated=False, path="file.py", comments=[bot_comment]),
            PRReviewThread(id="t2", is_resolved=False, is_outdated=False, path="file.py", comments=[human_comment])
        ]

        mock_github_client.get_pr_review_threads.return_value = threads

        result = fetch_pr_threads(mock_github_client, 42, include_resolved=False)

        assert len(result) == 1
        assert result[0].main_comment.author.login == "reviewer"

    def test_filters_empty_comments(self, mock_github_client, sample_github_user):
        """Test that empty comments are filtered out"""
        empty_comment = PRReviewComment(
            id=1, body="   ", author=sample_github_user,
            created_at="2025-01-01", updated_at="2025-01-01",
            path="file.py", line=1, diff_hunk=""
        )
        valid_comment = PRReviewComment(
            id=2, body="Good review", author=sample_github_user,
            created_at="2025-01-01", updated_at="2025-01-01",
            path="file.py", line=2, diff_hunk=""
        )

        threads = [
            PRReviewThread(id="t1", is_resolved=False, is_outdated=False, path="file.py", comments=[empty_comment]),
            PRReviewThread(id="t2", is_resolved=False, is_outdated=False, path="file.py", comments=[valid_comment])
        ]

        mock_github_client.get_pr_review_threads.return_value = threads

        result = fetch_pr_threads(mock_github_client, 42, include_resolved=False)

        assert len(result) == 1
        assert result[0].main_comment.body == "Good review"

    def test_filters_json_only_comments(self, mock_github_client, sample_github_user):
        """Test that JSON-only comments (coverage reports) are filtered"""
        json_comment = PRReviewComment(
            id=1, body='{"coverage": 85.5}', author=sample_github_user,
            created_at="2025-01-01", updated_at="2025-01-01",
            path="file.py", line=1, diff_hunk=""
        )
        normal_comment = PRReviewComment(
            id=2, body="Please fix this", author=sample_github_user,
            created_at="2025-01-01", updated_at="2025-01-01",
            path="file.py", line=2, diff_hunk=""
        )

        threads = [
            PRReviewThread(id="t1", is_resolved=False, is_outdated=False, path="file.py", comments=[json_comment]),
            PRReviewThread(id="t2", is_resolved=False, is_outdated=False, path="file.py", comments=[normal_comment])
        ]

        mock_github_client.get_pr_review_threads.return_value = threads

        result = fetch_pr_threads(mock_github_client, 42, include_resolved=False)

        assert len(result) == 1
        assert result[0].main_comment.body == "Please fix this"

    def test_includes_resolved_when_requested(self, mock_github_client, sample_github_user):
        """Test include_resolved parameter"""
        comment = PRReviewComment(
            id=1, body="Comment", author=sample_github_user,
            created_at="2025-01-01", updated_at="2025-01-01",
            path="file.py", line=1, diff_hunk=""
        )

        threads = [
            PRReviewThread(id="t1", is_resolved=True, is_outdated=False, path="file.py", comments=[comment])
        ]

        mock_github_client.get_pr_review_threads.return_value = threads

        result = fetch_pr_threads(mock_github_client, 42, include_resolved=True)

        mock_github_client.get_pr_review_threads.assert_called_with(42, include_resolved=True)
        assert len(result) == 1

    def test_handles_no_threads(self, mock_github_client):
        """Test with no review threads"""
        mock_github_client.get_pr_review_threads.return_value = []

        result = fetch_pr_threads(mock_github_client, 42, include_resolved=False)

        assert result == []


@pytest.mark.unit
class TestPushAndRequestReview:
    """Test push and review request operation"""

    def test_successful_push_and_rerequest(self, mock_github_client, mock_git_client):
        """Test successful push and review re-request"""
        success = push_and_request_review(
            mock_github_client,
            mock_git_client,
            "/tmp/worktree",
            "feature-branch",
            42,
            remote="origin"
        )

        assert success is True
        mock_git_client.run_in_worktree.assert_called_once_with(
            "/tmp/worktree",
            ["git", "push", "origin", "feature-branch"]
        )
        mock_github_client.request_pr_review.assert_called_once_with(42)

    def test_handles_push_failure(self, mock_github_client, mock_git_client):
        """Test handling of git push failure"""
        mock_git_client.run_in_worktree.side_effect = Exception("Push failed")

        success = push_and_request_review(
            mock_github_client,
            mock_git_client,
            "/tmp/worktree",
            "feature-branch",
            42
        )

        assert success is False

    def test_handles_review_request_failure(self, mock_github_client, mock_git_client):
        """Test handling of review request failure"""
        mock_github_client.request_pr_review.side_effect = Exception("API error")

        success = push_and_request_review(
            mock_github_client,
            mock_git_client,
            "/tmp/worktree",
            "feature-branch",
            42
        )

        assert success is False

    def test_uses_custom_remote(self, mock_github_client, mock_git_client):
        """Test using custom remote name"""
        push_and_request_review(
            mock_github_client,
            mock_git_client,
            "/tmp/worktree",
            "feature-branch",
            42,
            remote="upstream"
        )

        mock_git_client.run_in_worktree.assert_called_with(
            "/tmp/worktree",
            ["git", "push", "upstream", "feature-branch"]
        )
