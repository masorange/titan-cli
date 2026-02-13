"""
Unit tests for worktree operations
"""

import pytest
from titan_plugin_github.operations.worktree_operations import (
    setup_worktree,
    cleanup_worktree,
    commit_in_worktree,
    push_from_worktree,
)


@pytest.mark.unit
class TestSetupWorktree:
    """Test worktree setup"""

    def test_creates_worktree_successfully(self, mock_git_client):
        """Test successful worktree creation"""
        rel_path, abs_path, success = setup_worktree(
            mock_git_client,
            pr_number=123,
            branch="feature-branch",
            base_path=".titan/worktrees"
        )

        assert success is True
        assert rel_path == ".titan/worktrees/titan-review-123"
        assert "titan-review-123" in abs_path
        mock_git_client.create_worktree.assert_called_once()

    def test_removes_existing_worktree_before_creating(self, mock_git_client):
        """Test that existing worktree is removed first"""
        setup_worktree(mock_git_client, 123, "feature-branch")

        # Should attempt to remove first (might fail if doesn't exist)
        mock_git_client.remove_worktree.assert_called_once()
        mock_git_client.create_worktree.assert_called_once()

    def test_handles_creation_failure(self, mock_git_client):
        """Test handling of worktree creation failure"""
        mock_git_client.create_worktree.side_effect = Exception("Creation failed")

        rel_path, abs_path, success = setup_worktree(
            mock_git_client,
            123,
            "feature-branch"
        )

        assert success is False
        assert rel_path == ""
        assert abs_path == ""

    def test_uses_custom_base_path(self, mock_git_client):
        """Test using custom base path for worktrees"""
        rel_path, abs_path, success = setup_worktree(
            mock_git_client,
            456,
            "branch",
            base_path="/custom/path"
        )

        assert success is True
        assert rel_path == "/custom/path/titan-review-456"


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
        mock_git_client.remove_worktree.side_effect = Exception("Removal failed")

        success = cleanup_worktree(mock_git_client, "/path/to/worktree")

        assert success is False


@pytest.mark.unit
class TestCommitInWorktree:
    """Test creating commits in worktree"""

    def test_creates_commit_with_all_changes(self, mock_git_client):
        """Test creating commit with all changes staged"""
        mock_git_client.run_in_worktree.return_value = "abc123def456789"

        commit_hash = commit_in_worktree(
            mock_git_client,
            "/tmp/worktree",
            "Fix bug in module",
            add_all=True,
            no_verify=False
        )

        assert commit_hash == "abc123def456789"

        # Should call git add --all
        calls = mock_git_client.run_in_worktree.call_args_list
        assert any("add" in str(call) for call in calls)
        assert any("commit" in str(call) for call in calls)

    def test_creates_commit_without_staging(self, mock_git_client):
        """Test creating commit without staging changes"""
        mock_git_client.run_in_worktree.return_value = "def456abc123"

        commit_hash = commit_in_worktree(
            mock_git_client,
            "/tmp/worktree",
            "Commit message",
            add_all=False,
            no_verify=False
        )

        assert commit_hash == "def456abc123"

        # Should NOT call git add
        calls = mock_git_client.run_in_worktree.call_args_list
        assert not any("add" in str(call) and "--all" in str(call) for call in calls)

    def test_uses_no_verify_flag(self, mock_git_client):
        """Test using --no-verify flag to skip hooks"""
        mock_git_client.run_in_worktree.return_value = "hash123"

        commit_in_worktree(
            mock_git_client,
            "/tmp/worktree",
            "Message",
            add_all=False,
            no_verify=True
        )

        # Should include --no-verify in commit command
        calls = mock_git_client.run_in_worktree.call_args_list
        commit_call = [call for call in calls if "commit" in str(call)][0]
        assert "--no-verify" in str(commit_call)

    def test_returns_full_commit_hash(self, mock_git_client):
        """Test that full 40-char commit hash is returned"""
        full_hash = "a" * 40
        mock_git_client.run_in_worktree.return_value = full_hash

        commit_hash = commit_in_worktree(
            mock_git_client,
            "/tmp/worktree",
            "Test commit",
            add_all=True,
            no_verify=False
        )

        assert len(commit_hash) == 40
        assert commit_hash == full_hash

    def test_handles_commit_failure(self, mock_git_client):
        """Test handling of commit failure"""
        mock_git_client.run_in_worktree.side_effect = [
            None,  # git add succeeds
            Exception("Nothing to commit")  # git commit fails
        ]

        with pytest.raises(Exception, match="Nothing to commit"):
            commit_in_worktree(
                mock_git_client,
                "/tmp/worktree",
                "Message",
                add_all=True,
                no_verify=False
            )


@pytest.mark.unit
class TestPushFromWorktree:
    """Test pushing from worktree"""

    def test_pushes_with_explicit_branch(self, mock_git_client):
        """Test push with explicitly specified branch"""
        success = push_from_worktree(
            mock_git_client,
            "/tmp/worktree",
            remote="origin",
            branch="feature-branch",
            set_upstream=False
        )

        assert success is True
        mock_git_client.run_in_worktree.assert_called_with(
            "/tmp/worktree",
            ["git", "push", "origin", "feature-branch"]
        )

    def test_auto_detects_branch(self, mock_git_client):
        """Test auto-detection of current branch"""
        mock_git_client.run_in_worktree.side_effect = [
            "feature-branch",  # git branch --show-current
            None  # git push
        ]

        success = push_from_worktree(
            mock_git_client,
            "/tmp/worktree",
            remote="origin",
            branch=None,
            set_upstream=False
        )

        assert success is True
        calls = mock_git_client.run_in_worktree.call_args_list
        assert "branch" in str(calls[0])
        assert "push" in str(calls[1])

    def test_uses_set_upstream_flag(self, mock_git_client):
        """Test using -u flag to set upstream"""
        push_from_worktree(
            mock_git_client,
            "/tmp/worktree",
            remote="origin",
            branch="new-branch",
            set_upstream=True
        )

        mock_git_client.run_in_worktree.assert_called_with(
            "/tmp/worktree",
            ["git", "push", "-u", "origin", "new-branch"]
        )

    def test_handles_push_failure(self, mock_git_client):
        """Test handling of push failure"""
        mock_git_client.run_in_worktree.side_effect = Exception("Push rejected")

        success = push_from_worktree(
            mock_git_client,
            "/tmp/worktree",
            branch="feature"
        )

        assert success is False

    def test_handles_empty_branch_detection(self, mock_git_client):
        """Test handling when branch detection returns empty"""
        mock_git_client.run_in_worktree.return_value = ""

        success = push_from_worktree(
            mock_git_client,
            "/tmp/worktree",
            branch=None
        )

        assert success is False

    def test_uses_custom_remote(self, mock_git_client):
        """Test pushing to custom remote"""
        push_from_worktree(
            mock_git_client,
            "/tmp/worktree",
            remote="upstream",
            branch="main",
            set_upstream=False
        )

        mock_git_client.run_in_worktree.assert_called_with(
            "/tmp/worktree",
            ["git", "push", "upstream", "main"]
        )
