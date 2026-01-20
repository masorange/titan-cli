"""
Tests for prepare_commit_pr_data_step.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from titan_cli.engine import WorkflowContext
from titan_cli.engine.results import Success, Error
from titan_plugin_jira.steps.prepare_commit_pr_data_step import prepare_commit_pr_data_step


class TestPrepareCommitPRDataStep:
    """Tests for prepare_commit_pr_data_step."""

    @pytest.fixture
    def mock_context(self):
        """Create mock workflow context."""
        ctx = Mock(spec=WorkflowContext)
        ctx.get = Mock()
        ctx.set = Mock()
        ctx.data = {}
        ctx.textual = None
        ctx.ui = None
        ctx.views = None
        ctx.git = None
        ctx.github = None
        return ctx

    @pytest.fixture
    def mock_git_client(self):
        """Create mock git client."""
        git = Mock()
        git.get_current_branch = Mock(return_value="release-notes/26.4.0")
        return git

    @pytest.fixture
    def mock_github_client(self):
        """Create mock GitHub client."""
        github = Mock()
        github.get_current_user = Mock(return_value="testuser")
        github.list_labels = Mock(return_value=[
            "bug",
            "release notes 📜",
            "documentation"
        ])
        return github

    @pytest.fixture
    def mock_issues(self):
        """Create mock JIRA issues."""
        issue1 = Mock()
        issue1.key = "ECAPP-123"
        issue1.summary = "Fix login bug"

        issue2 = Mock()
        issue2.key = "ECAPP-124"
        issue2.summary = "Add new feature"

        return [issue1, issue2]

    # Success Paths

    def test_success_with_textual_ui(
        self, mock_context, mock_git_client, mock_github_client, mock_issues
    ):
        """Test successful execution with Textual UI."""

        # Setup context data
        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0",
            "platform": "iOS",
            "issues": mock_issues
        }.get(key, default)

        # Setup clients
        mock_context.git = mock_git_client
        mock_context.github = mock_github_client

        # Setup Textual UI
        mock_textual = Mock()
        mock_textual.text = Mock()
        mock_textual.mount = Mock()
        mock_context.textual = mock_textual

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert result
        assert isinstance(result, Success)
        assert "prepared" in result.message.lower()

        # Assert context was updated with all required data
        mock_context.set.assert_any_call("commit_message", "docs: Add release notes for 26.4.0")
        mock_context.set.assert_any_call("pr_title", "notes: Add release notes for 26.4.0")
        mock_context.set.assert_any_call("pr_head_branch", "release-notes/26.4.0")
        mock_context.set.assert_any_call("pr_base_branch", "develop")
        mock_context.set.assert_any_call("all_files", True)

        # Check pr_body was set (should contain template content)
        pr_body_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_body"]
        assert len(pr_body_calls) == 1
        pr_body = pr_body_calls[0][0][1]
        assert "26.4.0" in pr_body
        assert "Release Notes" in pr_body

        # Check labels were set
        label_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_labels"]
        assert len(label_calls) == 1
        labels = label_calls[0][0][1]
        assert labels == ["release notes 📜"]

        # Check assignees were set
        assignee_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_assignees"]
        assert len(assignee_calls) == 1
        assignees = assignee_calls[0][0][1]
        assert assignees == ["testuser"]

        # Assert UI was called
        mock_textual.text.assert_called()
        mock_textual.mount.assert_called()

    def test_success_with_rich_ui(
        self, mock_context, mock_git_client, mock_github_client, mock_issues
    ):
        """Test successful execution with Rich UI."""

        # Setup context data
        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0",
            "platform": "Android",
            "issues": mock_issues
        }.get(key, default)

        # Setup clients
        mock_context.git = mock_git_client
        mock_context.github = mock_github_client

        # Setup Rich UI
        mock_ui = Mock()
        mock_ui.text = Mock()
        mock_ui.text.info = Mock()
        mock_ui.panel = Mock()
        mock_ui.panel.print = Mock()
        mock_context.ui = mock_ui

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert
        assert isinstance(result, Success)
        mock_ui.text.info.assert_called()

    def test_success_with_default_platform(
        self, mock_context, mock_git_client, mock_github_client
    ):
        """Test successful execution with default platform (iOS)."""

        # Setup - no platform specified, should default to "iOS"
        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0",
            "issues": []
        }.get(key, default)

        mock_context.git = mock_git_client
        mock_context.github = mock_github_client
        mock_context.textual = Mock()
        mock_context.textual.text = Mock()
        mock_context.textual.mount = Mock()

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert - should use default platform "iOS"
        assert isinstance(result, Success)

        # Check pr_body contains "ios"
        pr_body_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_body"]
        pr_body = pr_body_calls[0][0][1]
        assert "ios" in pr_body.lower()

    def test_success_without_issues(
        self, mock_context, mock_git_client, mock_github_client
    ):
        """Test successful execution with no issues."""

        # Setup - no issues
        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0",
            "platform": "iOS",
            "issues": []
        }.get(key, default)

        mock_context.git = mock_git_client
        mock_context.github = mock_github_client
        mock_context.textual = Mock()
        mock_context.textual.text = Mock()
        mock_context.textual.mount = Mock()

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert - should still succeed with fallback message
        assert isinstance(result, Success)

        pr_body_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_body"]
        pr_body = pr_body_calls[0][0][1]
        assert "no se encontraron issues" in pr_body.lower() or "no issues" in pr_body.lower()

    def test_success_without_labels_found(
        self, mock_context, mock_git_client, mock_github_client
    ):
        """Test successful execution when no matching label found."""

        # Setup
        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0",
            "platform": "iOS",
            "issues": []
        }.get(key, default)

        mock_context.git = mock_git_client
        mock_context.github = mock_github_client

        # GitHub has no "release notes" label
        mock_github_client.list_labels.return_value = ["bug", "feature"]

        mock_context.textual = Mock()
        mock_context.textual.text = Mock()
        mock_context.textual.mount = Mock()

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert - should succeed without labels
        assert isinstance(result, Success)

        # pr_labels should not be set
        label_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_labels"]
        assert len(label_calls) == 0

    # Error Conditions

    def test_error_missing_fix_version(self, mock_context):
        """Test error when fix_version is missing."""

        # Setup - missing fix_version
        mock_context.get.return_value = None
        mock_context.textual = Mock()

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert
        assert isinstance(result, Error)
        assert "fix_version" in result.message.lower()

    def test_error_missing_git_client(self, mock_context):
        """Test error when git client is not available."""

        # Setup
        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0"
        }.get(key, default)

        # Git client is None
        mock_context.git = None
        mock_context.textual = Mock()

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert
        assert isinstance(result, Error)
        assert "gitclient not available" in result.message.lower()

    def test_error_get_current_branch_fails(
        self, mock_context, mock_git_client, mock_github_client
    ):
        """Test error when getting current branch fails."""

        # Setup
        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0"
        }.get(key, default)

        # Git client raises exception
        mock_git_client.get_current_branch.side_effect = Exception("Git error")

        mock_context.git = mock_git_client
        mock_context.github = mock_github_client
        mock_context.textual = Mock()

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert
        assert isinstance(result, Error)
        assert "error getting current branch" in result.message.lower()

    def test_handles_github_client_unavailable(
        self, mock_context, mock_git_client
    ):
        """Test graceful handling when GitHub client unavailable."""

        # Setup
        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0",
            "issues": []
        }.get(key, default)

        mock_context.git = mock_git_client
        mock_context.github = None  # No GitHub client

        mock_context.textual = Mock()
        mock_context.textual.text = Mock()
        mock_context.textual.mount = Mock()

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert - should succeed without labels/assignees
        assert isinstance(result, Success)

        # Labels should not be set
        label_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_labels"]
        assert len(label_calls) == 0

        # Assignees should not be set
        assignee_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_assignees"]
        assert len(assignee_calls) == 0

    def test_handles_github_get_current_user_fails(
        self, mock_context, mock_git_client, mock_github_client
    ):
        """Test graceful handling when GitHub get_current_user fails."""

        # Setup
        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0",
            "issues": []
        }.get(key, default)

        mock_context.git = mock_git_client
        mock_context.github = mock_github_client

        # GitHub get_current_user raises exception
        mock_github_client.get_current_user.side_effect = Exception("API error")

        mock_context.textual = Mock()
        mock_context.textual.text = Mock()
        mock_context.textual.mount = Mock()

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert - should succeed without assignees
        assert isinstance(result, Success)

        # Assignees should not be set
        assignee_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_assignees"]
        assert len(assignee_calls) == 0

    def test_handles_github_list_labels_fails(
        self, mock_context, mock_git_client, mock_github_client
    ):
        """Test graceful handling when GitHub list_labels fails."""

        # Setup
        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0",
            "issues": []
        }.get(key, default)

        mock_context.git = mock_git_client
        mock_context.github = mock_github_client

        # GitHub list_labels raises exception
        mock_github_client.list_labels.side_effect = Exception("API error")

        mock_context.textual = Mock()
        mock_context.textual.text = Mock()
        mock_context.textual.mount = Mock()

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert - should succeed without labels
        assert isinstance(result, Success)

        # Labels should not be set
        label_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_labels"]
        assert len(label_calls) == 0

    # Template and Data Formatting

    def test_template_loading_success(
        self, mock_context, mock_git_client, mock_github_client
    ):
        """Test that template loads correctly."""

        # Setup
        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0",
            "platform": "iOS",
            "issues": []
        }.get(key, default)

        mock_context.git = mock_git_client
        mock_context.github = mock_github_client
        mock_context.textual = Mock()
        mock_context.textual.text = Mock()
        mock_context.textual.mount = Mock()

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert template content
        pr_body_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_body"]
        pr_body = pr_body_calls[0][0][1]

        # Check template structure
        assert "Release Notes 26.4.0" in pr_body
        assert "📋 Resumen" in pr_body
        assert "📱 Plataforma" in pr_body
        assert "📝 Cambios Incluidos" in pr_body
        assert "🔍 Issues Incluidos" in pr_body

    def test_platform_checkbox_marked_ios(
        self, mock_context, mock_git_client, mock_github_client
    ):
        """Test that iOS checkbox is marked when platform is iOS."""

        # Setup
        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0",
            "platform": "iOS",
            "issues": []
        }.get(key, default)

        mock_context.git = mock_git_client
        mock_context.github = mock_github_client
        mock_context.textual = Mock()
        mock_context.textual.text = Mock()
        mock_context.textual.mount = Mock()

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert
        pr_body_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_body"]
        pr_body = pr_body_calls[0][0][1]

        assert "- [x] iOS" in pr_body
        assert "- [ ] Android" in pr_body

    def test_platform_checkbox_marked_android(
        self, mock_context, mock_git_client, mock_github_client
    ):
        """Test that Android checkbox is marked when platform is Android."""

        # Setup
        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0",
            "platform": "Android",
            "issues": []
        }.get(key, default)

        mock_context.git = mock_git_client
        mock_context.github = mock_github_client
        mock_context.textual = Mock()
        mock_context.textual.text = Mock()
        mock_context.textual.mount = Mock()

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert
        pr_body_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_body"]
        pr_body = pr_body_calls[0][0][1]

        assert "- [ ] iOS" in pr_body
        assert "- [x] Android" in pr_body

    def test_issue_list_formatting(
        self, mock_context, mock_git_client, mock_github_client, mock_issues
    ):
        """Test that issue list is formatted correctly."""

        # Setup
        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0",
            "platform": "iOS",
            "issues": mock_issues
        }.get(key, default)

        mock_context.git = mock_git_client
        mock_context.github = mock_github_client
        mock_context.textual = Mock()
        mock_context.textual.text = Mock()
        mock_context.textual.mount = Mock()

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert
        pr_body_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_body"]
        pr_body = pr_body_calls[0][0][1]

        # Check issue list contains all issues
        assert "[ECAPP-123] Fix login bug" in pr_body
        assert "[ECAPP-124] Add new feature" in pr_body

    def test_issue_list_truncation_with_many_issues(
        self, mock_context, mock_git_client, mock_github_client
    ):
        """Test that issue list is truncated when >10 issues."""

        # Setup - create 15 issues
        many_issues = []
        for i in range(15):
            issue = Mock()
            issue.key = f"ECAPP-{i}"
            issue.summary = f"Issue {i}"
            many_issues.append(issue)

        mock_context.get.side_effect = lambda key, default=None: {
            "fix_version": "26.4.0",
            "platform": "iOS",
            "issues": many_issues
        }.get(key, default)

        mock_context.git = mock_git_client
        mock_context.github = mock_github_client
        mock_context.textual = Mock()
        mock_context.textual.text = Mock()
        mock_context.textual.mount = Mock()

        # Execute
        result = prepare_commit_pr_data_step(mock_context)

        # Assert
        pr_body_calls = [call for call in mock_context.set.call_args_list if call[0][0] == "pr_body"]
        pr_body = pr_body_calls[0][0][1]

        # Should show "... y 5 issues más"
        assert "5 issues más" in pr_body
