"""
Tests for JIRA plugin confirmation steps (HITL).
"""

import pytest
from unittest.mock import Mock
from titan_cli.engine import WorkflowContext
from titan_cli.engine.results import Success, Error


class TestConfirmReleaseNotesStep:
    """Tests for confirm_release_notes_step."""

    @pytest.fixture
    def mock_context(self):
        """Create mock workflow context."""
        ctx = Mock(spec=WorkflowContext)
        ctx.get = Mock()
        ctx.textual = None
        ctx.ui = None
        ctx.views = None
        return ctx

    def test_confirm_with_textual_ui_accept(self, mock_context):
        """Test confirming release notes in Textual UI (user accepts)."""
        from titan_plugin_jira.steps.confirm_release_notes_step import confirm_release_notes_step

        # Setup - side_effect needs to accept default parameter
        mock_context.get.side_effect = lambda key, default=None: {
            "release_notes": "*🟣 Yoigo*\n- Test note (ECAPP-123)\n",
            "fix_version": "26.4",
            "total_issues": 5,
            "brand_counts": {"Yoigo": 3, "Jazztel": 2}
        }.get(key, default)

        mock_textual = Mock()
        mock_textual.text = Mock()
        mock_textual.mount = Mock()
        mock_textual.ask_confirm = Mock(return_value=True)
        mock_context.textual = mock_textual

        # Execute
        result = confirm_release_notes_step(mock_context)

        # Assert
        assert isinstance(result, Success)
        assert "confirmadas" in result.message.lower()
        assert result.metadata["confirmed"] is True
        mock_textual.ask_confirm.assert_called_once()

    def test_confirm_with_textual_ui_cancel(self, mock_context):
        """Test cancelling release notes in Textual UI (user cancels)."""
        from titan_plugin_jira.steps.confirm_release_notes_step import confirm_release_notes_step

        # Setup
        mock_context.get.side_effect = lambda key, default=None: {
            "release_notes": "*🟣 Yoigo*\n- Test note (ECAPP-123)\n",
            "fix_version": "26.4"
        }.get(key, default)

        mock_textual = Mock()
        mock_textual.text = Mock()
        mock_textual.mount = Mock()
        mock_textual.ask_confirm = Mock(return_value=False)
        mock_context.textual = mock_textual

        # Execute
        result = confirm_release_notes_step(mock_context)

        # Assert
        assert isinstance(result, Error)
        assert "cancelada" in result.message.lower()

    def test_confirm_missing_release_notes(self, mock_context):
        """Test error when release notes are missing."""
        from titan_plugin_jira.steps.confirm_release_notes_step import confirm_release_notes_step

        # Setup
        mock_context.get.return_value = None
        mock_context.textual = Mock()

        # Execute
        result = confirm_release_notes_step(mock_context)

        # Assert
        assert isinstance(result, Error)
        assert "no release notes available" in result.message.lower()


class TestConfirmCommitStep:
    """Tests for confirm_commit_step."""

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
    def mock_git_status(self):
        """Create mock git status."""
        status = Mock()
        status.modified_files = ["ReleaseNotes/release-notes-26.4.md"]
        status.untracked_files = []
        status.staged_files = []
        return status

    def test_confirm_commit_with_textual_ui_accept(self, mock_context, mock_git_status):
        """Test confirming commit in Textual UI (user accepts)."""
        from titan_plugin_jira.steps.confirm_commit_step import confirm_commit_step

        # Setup
        mock_git = Mock()
        mock_git.get_status = Mock(return_value=mock_git_status)
        mock_git.get_current_branch = Mock(return_value="release-notes/26.4")
        mock_context.git = mock_git

        mock_textual = Mock()
        mock_textual.text = Mock()
        mock_textual.mount = Mock()
        mock_textual.ask_confirm = Mock(return_value=True)
        mock_context.textual = mock_textual

        # Execute
        result = confirm_commit_step(mock_context)

        # Assert
        assert isinstance(result, Success)
        assert "confirmado" in result.message.lower()
        assert result.metadata["confirmed"] is True
        assert result.metadata["branch"] == "release-notes/26.4"

    def test_confirm_commit_cancel(self, mock_context, mock_git_status):
        """Test cancelling commit (user cancels)."""
        from titan_plugin_jira.steps.confirm_commit_step import confirm_commit_step

        # Setup
        mock_git = Mock()
        mock_git.get_status = Mock(return_value=mock_git_status)
        mock_git.get_current_branch = Mock(return_value="release-notes/26.4")
        mock_context.git = mock_git

        mock_textual = Mock()
        mock_textual.text = Mock()
        mock_textual.mount = Mock()
        mock_textual.ask_confirm = Mock(return_value=False)
        mock_context.textual = mock_textual

        # Execute
        result = confirm_commit_step(mock_context)

        # Assert
        assert isinstance(result, Error)
        assert "cancelado" in result.message.lower()

    def test_confirm_commit_no_git_client(self, mock_context):
        """Test error when git client is not available."""
        from titan_plugin_jira.steps.confirm_commit_step import confirm_commit_step

        # Setup
        mock_context.git = None
        mock_context.textual = Mock()

        # Execute
        result = confirm_commit_step(mock_context)

        # Assert
        assert isinstance(result, Error)
        assert "gitclient not available" in result.message.lower()
