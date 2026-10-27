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
    build_ai_review_prompt,
    build_commit_message_context,
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
class TestBuildAIReviewPrompt:
    """Test AI review prompt building"""

    def test_includes_response_file_path(self):
        """Test that response_file path appears in the prompt"""
        prompt = build_ai_review_prompt("/tmp/titan-ai-response-comment-123.txt")

        assert "/tmp/titan-ai-response-comment-123.txt" in prompt

    def test_preserves_context_placeholder(self):
        """Test that {context} placeholder is preserved for later substitution"""
        prompt = build_ai_review_prompt("/tmp/response.txt")

        assert "{context}" in prompt

    def test_different_paths_produce_different_prompts(self):
        """Test that different response file paths produce different prompts"""
        prompt_a = build_ai_review_prompt("/tmp/response-111.txt")
        prompt_b = build_ai_review_prompt("/tmp/response-222.txt")

        assert prompt_a != prompt_b
        assert "/tmp/response-111.txt" in prompt_a
        assert "/tmp/response-222.txt" in prompt_b

    def test_prompt_contains_key_instructions(self):
        """Test that the prompt includes the core task instructions"""
        prompt = build_ai_review_prompt("/tmp/response.txt")

        assert "Your Task" in prompt
        assert "code changes" in prompt
        assert "Ctrl+C" in prompt


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

    def test_uses_the_generated_subject_when_there_is_one(self):
        """The AI subject replaces `Fix: <file>`, which names the comment's file."""
        msg = create_commit_message(
            "Fix the bug in authentication",
            "reviewer123",
            "src/auth.py",
            comment_line=42,
            subject="fix: Reject expired tokens before refreshing them",
        )

        assert msg.splitlines()[0] == "fix: Reject expired tokens before refreshing them"
        assert "Fix: auth.py" not in msg
        assert "By: reviewer123" in msg

    def test_body_names_the_comment_it_answers(self):
        """The history has to be readable without opening the thread."""
        msg = create_commit_message(
            "Fix the bug", "reviewer123", "src/auth.py", comment_line=42, subject="fix: Do it"
        )

        assert "Addresses the review comment by @reviewer123 on src/auth.py:42." in msg

    def test_body_without_a_line(self):
        """A general comment has no line, and the reference drops it rather than saying None."""
        msg = create_commit_message("Fix the bug", "reviewer123", None, subject="fix: Do it")

        assert "Addresses the review comment by @reviewer123." in msg
        assert "None" not in msg

    def test_blank_subject_falls_back(self):
        """An empty answer from the model must not produce an empty subject line."""
        msg = create_commit_message("body", "reviewer123", "src/auth.py", subject="   ")

        assert msg.splitlines()[0] == "Fix: auth.py"


@pytest.mark.unit
class TestBuildCommitMessageContext:
    """Test the 'why' handed to the commit-message model"""

    def test_includes_where_and_the_whole_conversation(self, sample_ui_comment_thread):
        context = build_commit_message_context(sample_ui_comment_thread)

        assert "src/main.py:42" in context
        assert "@test-user" in context
        assert "This needs to be fixed" in context

    def test_keeps_the_end_when_the_thread_is_long(self, sample_ui_comment_thread):
        """The newest reply is what the fix answers, so it is the part that survives."""
        thread = sample_ui_comment_thread
        thread.main_comment.body = "x" * 5000

        context = build_commit_message_context(thread, max_chars=200)

        assert len(context) <= 200
        assert context.startswith("…")
        assert thread.replies[-1].body in context


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


