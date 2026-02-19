"""
Unit tests for worktree operations
"""

import pytest
from titan_cli.core.result import ClientError
from titan_plugin_github.operations.worktree_operations import (
    setup_worktree,
    cleanup_worktree,
    commit_in_worktree,
)


@pytest.mark.unit
class TestSetupWorktree:
    """Test worktree setup"""

    def test_creates_worktree_successfully(self, mock_git_client):
        """Test successful worktree creation"""
        abs_path, success = setup_worktree(
            mock_git_client,
            pr_number=123,
            branch="feature-branch",
            base_path=".titan/worktrees"
        )

        assert success is True
        assert "titan-review-123" in abs_path
        mock_git_client.create_worktree.assert_called_once()

    def test_removes_existing_worktree_before_creating(self, mock_git_client):
        """Test that existing worktree is removed first"""
        setup_worktree(mock_git_client, 123, "feature-branch")

        mock_git_client.remove_worktree.assert_called_once()
        mock_git_client.create_worktree.assert_called_once()

    def test_handles_creation_failure(self, mock_git_client):
        """Test handling of worktree creation failure"""
        from titan_cli.core.result import ClientError
        mock_git_client.create_worktree.return_value = ClientError(
            error_message="Creation failed", error_code="WORKTREE_CREATE_ERROR"
        )

        abs_path, success = setup_worktree(mock_git_client, 123, "feature-branch")

        assert success is False
        assert abs_path == ""

    def test_uses_custom_base_path(self, mock_git_client):
        """Test using custom base path for worktrees"""
        abs_path, success = setup_worktree(
            mock_git_client,
            456,
            "branch",
            base_path="/custom/path"
        )

        assert success is True
        assert "titan-review-456" in abs_path


@pytest.mark.unit
class TestCleanupWorktree:
    """Test worktree cleanup"""

    def test_removes_worktree_successfully(self, mock_git_client):
        """Test successful worktree removal"""
        success = cleanup_worktree(mock_git_client, ".titan/worktrees/titan-review-123")

        assert success is True
        mock_git_client.remove_worktree.assert_called_once_with(
            ".titan/worktrees/titan-review-123",
            force=True
        )

    def test_handles_removal_failure(self, mock_git_client):
        """Test handling of removal failure"""
        mock_git_client.remove_worktree.return_value = ClientError(
            error_message="Removal failed", error_code="WORKTREE_REMOVE_ERROR"
        )

        success = cleanup_worktree(mock_git_client, "/path/to/worktree")

        assert success is False


@pytest.mark.unit
class TestCommitInWorktree:
    """Test creating commits in worktree"""

    def test_creates_commit_with_all_changes(self, mock_git_client):
        """Test creating commit with all changes staged"""
        commit_hash = commit_in_worktree(
            mock_git_client,
            "/tmp/worktree",
            "Fix bug in module",
            add_all=True,
            no_verify=False
        )

        assert commit_hash == "abc123def456789abc123def456789abc1234567"
        mock_git_client.commit_in_worktree.assert_called_once_with(
            "/tmp/worktree", "Fix bug in module", True, False
        )

    def test_creates_commit_without_staging(self, mock_git_client):
        """Test creating commit without staging changes"""
        commit_in_worktree(
            mock_git_client,
            "/tmp/worktree",
            "Commit message",
            add_all=False,
            no_verify=False
        )

        mock_git_client.commit_in_worktree.assert_called_once_with(
            "/tmp/worktree", "Commit message", False, False
        )

    def test_uses_no_verify_flag(self, mock_git_client):
        """Test passing no_verify flag through to client"""
        commit_in_worktree(
            mock_git_client,
            "/tmp/worktree",
            "Message",
            add_all=False,
            no_verify=True
        )

        mock_git_client.commit_in_worktree.assert_called_once_with(
            "/tmp/worktree", "Message", False, True
        )

    def test_handles_commit_failure(self, mock_git_client):
        """Test handling of commit failure"""
        mock_git_client.commit_in_worktree.return_value = ClientError(
            error_message="Nothing to commit", error_code="WORKTREE_COMMIT_ERROR"
        )

        with pytest.raises(Exception, match="Failed to commit in worktree"):
            commit_in_worktree(
                mock_git_client,
                "/tmp/worktree",
                "Message",
                add_all=True,
                no_verify=False
            )
