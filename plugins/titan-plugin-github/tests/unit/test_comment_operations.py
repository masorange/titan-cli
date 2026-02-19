"""
Unit tests for comment operations
"""

import pytest
import tempfile
import os
from unittest.mock import patch
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_github.operations.comment_operations import (
    build_ai_review_context,
    find_ai_response_file,
    create_commit_message,
    reply_to_comment_batch,
)


@pytest.mark.unit
class TestBuildAIReviewContext:
    """Test building AI review context"""

    def test_builds_context_with_all_fields(self, sample_ui_comment_thread):
        """Test building context with complete thread"""
        context = build_ai_review_context(sample_ui_comment_thread, "feat: Add feature")

        assert context["pr"] == "feat: Add feature"
        assert context["file"] == "src/main.py"
        assert context["line"] == 42
        assert "thread" in context
        assert len(context["thread"]) == 2  # Main comment + 1 reply
        assert context["thread"][0]["author"] == "test-user"
        assert context["thread"][0]["body"] == "This needs to be fixed"

    def test_builds_context_without_replies(self, sample_review_comment):
        """Test building context with only main comment"""
        from titan_plugin_github.models.view import UICommentThread, UIComment

        # Convert network model to view model
        main_comment = UIComment.from_review_comment(sample_review_comment, is_outdated=False)

        thread = UICommentThread(
            thread_id="thread_solo",
            main_comment=main_comment,
            replies=[],
            is_resolved=False,
            is_outdated=False
        )

        context = build_ai_review_context(thread, "fix: Bug fix")

        assert len(context["thread"]) == 1
        assert context["pr"] == "fix: Bug fix"

    def test_handles_missing_diff_hunk(self, sample_ui_comment_thread):
        """Test context building when diff_hunk is None"""
        sample_ui_comment_thread.main_comment.diff_hunk = None

        context = build_ai_review_context(sample_ui_comment_thread, "test: Add test")

        assert context["diff_hunk"] is None



@pytest.mark.unit
class TestFindAIResponseFile:
    """Test AI response file finding"""

    def test_finds_file_at_expected_path(self):
        """Test finding file at primary location"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("test response")
            temp_path = f.name

        try:
            result = find_ai_response_file(123, temp_path)
            assert result == temp_path
        finally:
            os.unlink(temp_path)

    def test_returns_none_when_not_found(self):
        """Test returns None when file doesn't exist"""
        result = find_ai_response_file(999, "/nonexistent/path/file.txt")
        assert result is None

    @patch('glob.glob')
    def test_searches_fallback_locations(self, mock_glob):
        """Test searching in common AI CLI directories"""
        mock_glob.return_value = ["/home/user/.gemini/tmp/response.txt"]

        result = find_ai_response_file(123, "/tmp/response.txt")

        assert result == "/home/user/.gemini/tmp/response.txt"
        assert mock_glob.called


@pytest.mark.unit
class TestCreateCommitMessage:
    """Test commit message creation"""

    def test_creates_message_with_path(self):
        """Test creating commit message with file path"""
        msg = create_commit_message(
            "Fix the bug in authentication",
            "reviewer123",
            "src/auth.py"
        )

        assert "Fix: auth.py" in msg
        assert "By: reviewer123" in msg

    def test_creates_message_without_path(self):
        """Test creating commit message without file path"""
        msg = create_commit_message(
            "Update documentation",
            "reviewer456",
            None
        )

        assert "PR review fix" in msg
        assert "By: reviewer456" in msg


@pytest.mark.unit
class TestReplyToCommentBatch:
    """Test batch comment replies"""

    def test_replies_to_all_comments_successfully(self, mock_github_client):
        """Test successful batch replies"""
        # Mock to return ClientSuccess
        mock_github_client.reply_to_comment.return_value = ClientSuccess(
            data=None, message="Comment posted"
        )

        replies = {
            101: "abc123",
            102: "Done",
            103: "Implemented"
        }

        results = reply_to_comment_batch(mock_github_client, 42, replies)

        assert len(results) == 3
        assert all(results.values())  # All should be True
        assert mock_github_client.reply_to_comment.call_count == 3

    def test_handles_partial_failures(self, mock_github_client):
        """Test handling when some replies fail"""
        def side_effect(pr_num, comment_id, text):
            if comment_id == 102:
                return ClientError(error_message="API Error", error_code="API_ERROR")
            return ClientSuccess(data=None, message="Comment posted")

        mock_github_client.reply_to_comment.side_effect = side_effect

        replies = {
            101: "Success",
            102: "Will fail",
            103: "Success"
        }

        results = reply_to_comment_batch(mock_github_client, 42, replies)

        assert results[101] is True
        assert results[102] is False
        assert results[103] is True

    def test_handles_empty_replies(self, mock_github_client):
        """Test with no replies to send"""
        results = reply_to_comment_batch(mock_github_client, 42, {})

        assert results == {}
        assert not mock_github_client.reply_to_comment.called


