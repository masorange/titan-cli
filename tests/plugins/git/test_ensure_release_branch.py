"""
Tests for Git plugin ensure_release_branch step.
"""

import pytest
from unittest.mock import Mock
from titan_cli.engine import WorkflowContext
from titan_cli.engine.results import Success, Error


class TestEnsureReleaseBranchStep:
    """Tests for ensure_release_branch_step."""

    @pytest.fixture
    def mock_context(self):
        """Create mock workflow context."""
        ctx = Mock(spec=WorkflowContext)
        ctx.get = Mock(return_value="26.4")
        ctx.textual = None
        ctx.ui = None
        ctx.views = None
        return ctx

    @pytest.fixture
    def mock_git_client(self):
        """Create mock git client."""
        git = Mock()
        git.get_current_branch = Mock()
        git.get_branches = Mock()
        git.checkout = Mock()
        git.pull = Mock()
        git.create_branch = Mock()
        return git

    def test_already_on_correct_branch(self, mock_context, mock_git_client):
        """Test when already on the correct release notes branch."""
        from titan_plugin_git.steps.ensure_release_branch_step import ensure_release_branch_step

        # Setup
        mock_git_client.get_current_branch.return_value = "release-notes/26.4"
        mock_context.git = mock_git_client

        # Execute
        result = ensure_release_branch_step(mock_context)

        # Assert
        assert isinstance(result, Success)
        assert "already on" in result.message.lower()
        assert result.metadata["release_branch"] == "release-notes/26.4"
        assert result.metadata["branch_created"] is False

        # Should not checkout, pull, or create
        mock_git_client.checkout.assert_not_called()
        mock_git_client.pull.assert_not_called()
        mock_git_client.create_branch.assert_not_called()

    def test_branch_exists_switch_to_it(self, mock_context, mock_git_client):
        """Test when branch exists but we're on develop - should just switch to it."""
        from titan_plugin_git.steps.ensure_release_branch_step import ensure_release_branch_step

        # Setup
        mock_git_client.get_current_branch.return_value = "develop"
        mock_git_client.get_branches.return_value = [
            "develop",
            "master",
            "release-notes/26.4"  # Branch exists
        ]
        mock_context.git = mock_git_client

        # Execute
        result = ensure_release_branch_step(mock_context)

        # Assert
        assert isinstance(result, Success)
        assert "switched to" in result.message.lower() or "existing" in result.message.lower()
        assert result.metadata["release_branch"] == "release-notes/26.4"
        assert result.metadata["branch_created"] is False

        # Should only checkout the existing branch (no longer checks out develop first)
        assert mock_git_client.checkout.call_count == 1
        mock_git_client.checkout.assert_called_once_with("release-notes/26.4")
        # Should not pull anymore (workflow starts from current branch)
        mock_git_client.pull.assert_not_called()

        # Should NOT create branch
        mock_git_client.create_branch.assert_not_called()

    def test_branch_does_not_exist_create_it(self, mock_context, mock_git_client):
        """Test when branch doesn't exist - should create it from current branch."""
        from titan_plugin_git.steps.ensure_release_branch_step import ensure_release_branch_step

        # Setup
        mock_git_client.get_current_branch.return_value = "develop"
        mock_git_client.get_branches.return_value = [
            "develop",
            "master"
            # release-notes/26.4 does NOT exist
        ]
        mock_context.git = mock_git_client

        # Execute
        result = ensure_release_branch_step(mock_context)

        # Assert
        assert isinstance(result, Success)
        assert "created" in result.message.lower()
        assert result.metadata["release_branch"] == "release-notes/26.4"
        assert result.metadata["branch_created"] is True

        # Should create branch from current (develop), then checkout new branch
        assert mock_git_client.checkout.call_count == 1
        mock_git_client.checkout.assert_called_once_with("release-notes/26.4")
        # Should not pull anymore (workflow starts from current branch)
        mock_git_client.pull.assert_not_called()
        # Should create branch from current branch (develop)
        mock_git_client.create_branch.assert_called_once_with(
            "release-notes/26.4",
            start_point="develop"
        )

    def test_missing_fix_version(self, mock_context, mock_git_client):
        """Test error when fix_version is missing."""
        from titan_plugin_git.steps.ensure_release_branch_step import ensure_release_branch_step

        # Setup
        mock_context.get.return_value = None
        mock_context.git = mock_git_client

        # Execute
        result = ensure_release_branch_step(mock_context)

        # Assert
        assert isinstance(result, Error)
        assert "fix_version is required" in result.message.lower()

    def test_no_git_client(self, mock_context):
        """Test error when git client is not available."""
        from titan_plugin_git.steps.ensure_release_branch_step import ensure_release_branch_step

        # Setup
        mock_context.git = None

        # Execute
        result = ensure_release_branch_step(mock_context)

        # Assert
        assert isinstance(result, Error)
        assert "git client not available" in result.message.lower()

    def test_git_operation_fails(self, mock_context, mock_git_client):
        """Test error handling when git operation fails."""
        from titan_plugin_git.steps.ensure_release_branch_step import ensure_release_branch_step

        # Setup
        mock_git_client.get_current_branch.side_effect = Exception("Git error")
        mock_context.git = mock_git_client

        # Execute
        result = ensure_release_branch_step(mock_context)

        # Assert
        assert isinstance(result, Error)
        assert "failed to ensure release branch" in result.message.lower()
        assert "git error" in result.message.lower()
