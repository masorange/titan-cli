"""
Unit tests for Status Service
"""

import pytest
from unittest.mock import Mock
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_git.clients.services.status_service import StatusService
from titan_plugin_git.exceptions import GitCommandError


@pytest.fixture
def mock_git_network():
    """Mock GitNetwork instance"""
    return Mock()


@pytest.mark.unit
class TestStatusServiceGetStatus:
    """Test StatusService.get_status()"""

    def test_get_status_clean(self, mock_git_network):
        """Test getting status for clean repository"""
        mock_git_network.run_command.side_effect = [
            "main",  # current branch
            "",  # git status --short (clean)
            "0\t0",  # upstream status
        ]

        service = StatusService(mock_git_network)
        result = service.get_status()

        assert isinstance(result, ClientSuccess)
        assert result.data.branch == "main"
        assert result.data.is_clean is True
        assert result.data.clean_icon == "✓"
        assert result.data.status_summary == "Clean"
        assert result.data.sync_status == "synced"

    def test_get_status_with_modified_files(self, mock_git_network):
        """Test getting status with modified files"""
        mock_git_network.run_command.side_effect = [
            "feature",  # current branch
            " M file1.py\n M file2.py",  # git status --short
            "2\t1",  # upstream status (2 ahead, 1 behind)
        ]

        service = StatusService(mock_git_network)
        result = service.get_status()

        assert isinstance(result, ClientSuccess)
        assert result.data.branch == "feature"
        assert result.data.is_clean is False
        assert result.data.clean_icon == "✗"
        assert len(result.data.modified_files) == 2
        assert "2 modified" in result.data.status_summary
        assert result.data.ahead == 2
        assert result.data.behind == 1
        assert result.data.sync_status == "↑2 ↓1"

    def test_get_status_with_untracked_files(self, mock_git_network):
        """Test getting status with untracked files"""
        mock_git_network.run_command.side_effect = [
            "main",
            "?? new_file.py\n?? another.py",
            "0\t0",
        ]

        service = StatusService(mock_git_network)
        result = service.get_status()

        assert isinstance(result, ClientSuccess)
        assert len(result.data.untracked_files) == 2
        assert "2 untracked" in result.data.status_summary

    def test_get_status_with_staged_files(self, mock_git_network):
        """Test getting status with staged files"""
        mock_git_network.run_command.side_effect = [
            "main",
            "M  staged.py\nA  new.py",
            "0\t0",
        ]

        service = StatusService(mock_git_network)
        result = service.get_status()

        assert isinstance(result, ClientSuccess)
        assert len(result.data.staged_files) == 2
        assert "2 staged" in result.data.status_summary

    def test_get_status_ahead_only(self, mock_git_network):
        """Test status when ahead of remote"""
        mock_git_network.run_command.side_effect = [
            "main",
            "",
            "3\t0",  # 3 ahead, 0 behind
        ]

        service = StatusService(mock_git_network)
        result = service.get_status()

        assert isinstance(result, ClientSuccess)
        assert result.data.ahead == 3
        assert result.data.behind == 0
        assert result.data.sync_status == "↑3"

    def test_get_status_behind_only(self, mock_git_network):
        """Test status when behind remote"""
        mock_git_network.run_command.side_effect = [
            "main",
            "",
            "0\t2",  # 0 ahead, 2 behind
        ]

        service = StatusService(mock_git_network)
        result = service.get_status()

        assert isinstance(result, ClientSuccess)
        assert result.data.ahead == 0
        assert result.data.behind == 2
        assert result.data.sync_status == "↓2"

    def test_get_status_error(self, mock_git_network):
        """Test error when getting status"""
        mock_git_network.run_command.side_effect = GitCommandError("Failed")

        service = StatusService(mock_git_network)
        result = service.get_status()

        assert isinstance(result, ClientError)


@pytest.mark.unit
class TestStatusServiceHasUncommittedChanges:
    """Test StatusService.has_uncommitted_changes()"""

    def test_has_uncommitted_changes_true(self, mock_git_network):
        """Test repository has uncommitted changes"""
        mock_git_network.run_command.return_value = "M  file.py\n"

        service = StatusService(mock_git_network)
        result = service.has_uncommitted_changes()

        assert isinstance(result, ClientSuccess)
        assert result.data is True

    def test_has_uncommitted_changes_false(self, mock_git_network):
        """Test repository has no uncommitted changes"""
        mock_git_network.run_command.return_value = ""

        service = StatusService(mock_git_network)
        result = service.has_uncommitted_changes()

        assert isinstance(result, ClientSuccess)
        assert result.data is False

    def test_has_uncommitted_changes_error(self, mock_git_network):
        """Test error checking uncommitted changes"""
        mock_git_network.run_command.side_effect = GitCommandError("Failed")

        service = StatusService(mock_git_network)
        result = service.has_uncommitted_changes()

        assert isinstance(result, ClientError)
