"""
Unit tests for comment operations
"""

import pytest
import tempfile
import os
from unittest.mock import patch
from titan_plugin_github.operations.comment_operations import (
    build_ai_review_context,
    detect_worktree_changes,
    find_ai_response_file,
    create_commit_message,
    reply_to_comment_batch,
    auto_review_comment,
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
class TestDetectWorktreeChanges:
    """Test worktree change detection"""

    def test_detects_new_changes(self):
        """Test detection of new file changes"""
        before = "M file1.txt\nM file2.txt"
        after = "M file1.txt\nM file2.txt\nM file3.txt\nA file4.txt"

        has_changes, changed_files = detect_worktree_changes(before, after)

        assert has_changes is True
        assert len(changed_files) == 2
        assert "M file3.txt" in changed_files
        assert "A file4.txt" in changed_files

    def test_no_changes_detected(self):
        """Test when no new changes exist"""
        status = "M file1.txt\nM file2.txt"

        has_changes, changed_files = detect_worktree_changes(status, status)

        assert has_changes is False
        assert len(changed_files) == 0

    def test_handles_empty_status(self):
        """Test with empty git status"""
        has_changes, changed_files = detect_worktree_changes("", "M newfile.txt")

        assert has_changes is True
        assert "M newfile.txt" in changed_files

    def test_handles_removed_files(self):
        """Test when files are removed (staged → unstaged)"""
        before = "M file1.txt\nM file2.txt"
        after = "M file1.txt"

        has_changes, changed_files = detect_worktree_changes(before, after)

        # No NEW changes, just removal
        assert has_changes is False


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

    def test_creates_message_with_all_info(self):
        """Test creating commit message with complete info"""
        msg = create_commit_message(
            "Fix the bug in authentication",
            "reviewer123",
            "src/auth.py"
        )

        assert "Fix PR comment: Fix the bug in authentication" in msg
        assert "Comment by reviewer123" in msg
        assert "on src/auth.py" in msg

    def test_creates_message_without_path(self):
        """Test creating commit message without file path"""
        msg = create_commit_message(
            "Update documentation",
            "reviewer456",
            None
        )

        assert "Fix PR comment: Update documentation" in msg
        assert "Comment by reviewer456" in msg
        assert "on " not in msg.split("Comment by reviewer456")[-1]

    def test_truncates_long_comments(self):
        """Test truncation of very long comment bodies"""
        long_comment = "a" * 200
        msg = create_commit_message(long_comment, "user", "file.py")

        # Should be truncated to 80 chars
        assert len(msg.split('\n')[0]) <= 100  # "Fix PR comment: " + 80 chars


@pytest.mark.unit
class TestReplyToCommentBatch:
    """Test batch comment replies"""

    def test_replies_to_all_comments_successfully(self, mock_github_client):
        """Test successful batch replies"""
        replies = {
            101: "Fixed in abc123",
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
                raise Exception("API Error")

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


@pytest.mark.unit
class TestAutoReviewComment:
    """Test automatic comment review with AI"""

    def test_commits_when_ai_makes_code_changes(
        self, mock_github_client, mock_git_client, sample_ui_comment_thread
    ):
        """Test commit creation when AI makes code changes"""
        # Mock git status showing changes
        mock_git_client.run_in_worktree.side_effect = [
            "",  # Before: clean (git status --short)
            "M src/file.py",  # After: changes (git status --short)
            None,  # git add --all
            None,  # git commit
            "abc123def456"  # git rev-parse HEAD (commit hash)
        ]

        # Mock AI executor
        def ai_executor(context, response_file):
            pass  # AI makes changes

        has_changes, commit_hash, response = auto_review_comment(
            mock_github_client,
            mock_git_client,
            sample_ui_comment_thread,
            "/tmp/worktree",
            "feat: Add feature",
            "/tmp/response.txt",
            ai_executor
        )

        assert has_changes is True
        assert commit_hash == "abc123def456"
        assert response is None

    def test_returns_text_response_when_no_code_changes(
        self, mock_github_client, mock_git_client, sample_ui_comment_thread
    ):
        """Test text response when AI doesn't make code changes"""
        # Mock git status showing NO changes
        mock_git_client.run_in_worktree.side_effect = [
            "",  # Before: clean
            ""   # After: still clean
        ]

        # Create temp response file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This comment doesn't apply because...")
            response_path = f.name

        try:
            def ai_executor(context, response_file):
                pass  # AI writes response to file

            has_changes, commit_hash, response = auto_review_comment(
                mock_github_client,
                mock_git_client,
                sample_ui_comment_thread,
                "/tmp/worktree",
                "feat: Add feature",
                response_path,
                ai_executor
            )

            assert has_changes is False
            assert commit_hash is None
            assert "This comment doesn't apply" in response
        finally:
            os.unlink(response_path)

    def test_handles_ai_executor_failure(
        self, mock_github_client, mock_git_client, sample_ui_comment_thread
    ):
        """Test handling when AI executor fails"""
        mock_git_client.run_in_worktree.return_value = ""

        def failing_ai_executor(context, response_file):
            raise Exception("AI service unavailable")

        with pytest.raises(Exception, match="AI service unavailable"):
            auto_review_comment(
                mock_github_client,
                mock_git_client,
                sample_ui_comment_thread,
                "/tmp/worktree",
                "feat: Add feature",
                "/tmp/response.txt",
                failing_ai_executor
            )
