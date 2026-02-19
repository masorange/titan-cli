"""
Unit tests for Stash Service
"""

import pytest
from unittest.mock import Mock
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_git.clients.services.stash_service import StashService
from titan_plugin_git.exceptions import GitCommandError


@pytest.fixture
def mock_git_network():
    """Mock GitNetwork instance"""
    return Mock()


@pytest.fixture
def service(mock_git_network):
    return StashService(mock_git_network)


@pytest.mark.unit
class TestStashServicePush:
    """Test StashService.stash_push()"""

    def test_push_with_custom_message(self, service, mock_git_network):
        """Test stash push uses provided message"""
        mock_git_network.run_command.return_value = ""

        result = service.stash_push("my-stash")

        assert isinstance(result, ClientSuccess)
        assert result.data is True
        mock_git_network.run_command.assert_called_once_with(
            ["git", "stash", "push", "-m", "my-stash"]
        )

    def test_push_without_message_uses_default(self, service, mock_git_network):
        """Test stash push without message generates timestamp-based message"""
        mock_git_network.run_command.return_value = ""

        result = service.stash_push()

        assert isinstance(result, ClientSuccess)
        args = mock_git_network.run_command.call_args.args[0]
        assert args[:3] == ["git", "stash", "push"]
        assert "-m" in args

    def test_push_error_returns_client_error(self, service, mock_git_network):
        """Test git error returns ClientError"""
        mock_git_network.run_command.side_effect = GitCommandError("no local changes")

        result = service.stash_push("msg")

        assert isinstance(result, ClientError)
        assert result.error_code == "STASH_ERROR"
        assert "no local changes" in result.error_message


@pytest.mark.unit
class TestStashServicePop:
    """Test StashService.stash_pop()"""

    def test_pop_latest_stash(self, service, mock_git_network):
        """Test pop without ref uses latest stash"""
        mock_git_network.run_command.return_value = ""

        result = service.stash_pop()

        assert isinstance(result, ClientSuccess)
        assert result.data is True
        mock_git_network.run_command.assert_called_once_with(["git", "stash", "pop"])

    def test_pop_specific_stash_ref(self, service, mock_git_network):
        """Test pop with specific stash ref"""
        mock_git_network.run_command.return_value = ""

        result = service.stash_pop("stash@{2}")

        assert isinstance(result, ClientSuccess)
        mock_git_network.run_command.assert_called_once_with(
            ["git", "stash", "pop", "stash@{2}"]
        )

    def test_pop_error_returns_client_error(self, service, mock_git_network):
        """Test git error returns ClientError"""
        mock_git_network.run_command.side_effect = GitCommandError("conflict during pop")

        result = service.stash_pop()

        assert isinstance(result, ClientError)
        assert result.error_code == "STASH_POP_ERROR"


@pytest.mark.unit
class TestStashServiceFindByMessage:
    """Test StashService.find_stash_by_message()"""

    def test_finds_stash_by_message(self, service, mock_git_network):
        """Test finds stash ref when message matches"""
        mock_git_network.run_command.return_value = (
            "stash@{0}: On main: my-stash\n"
            "stash@{1}: On main: other-stash\n"
        )

        result = service.find_stash_by_message("my-stash")

        assert isinstance(result, ClientSuccess)
        assert result.data == "stash@{0}"

    def test_returns_none_when_not_found(self, service, mock_git_network):
        """Test returns None when no stash matches"""
        mock_git_network.run_command.return_value = "stash@{0}: On main: other\n"

        result = service.find_stash_by_message("missing-stash")

        assert isinstance(result, ClientSuccess)
        assert result.data is None

    def test_empty_stash_list_returns_none(self, service, mock_git_network):
        """Test empty stash list returns None"""
        mock_git_network.run_command.return_value = ""

        result = service.find_stash_by_message("anything")

        assert isinstance(result, ClientSuccess)
        assert result.data is None

    def test_error_returns_client_error(self, service, mock_git_network):
        """Test git error returns ClientError"""
        mock_git_network.run_command.side_effect = GitCommandError("not a git repo")

        result = service.find_stash_by_message("msg")

        assert isinstance(result, ClientError)
        assert result.error_code == "STASH_FIND_ERROR"


@pytest.mark.unit
class TestStashServiceRestoreStash:
    """Test StashService.restore_stash()"""

    def test_restore_found_stash(self, service, mock_git_network):
        """Test restore pops the stash when found"""
        mock_git_network.run_command.side_effect = [
            "stash@{0}: On main: my-stash\n",  # stash list
            "",                                  # stash pop
        ]

        result = service.restore_stash("my-stash")

        assert isinstance(result, ClientSuccess)
        assert result.data is True

    def test_restore_not_found_returns_false(self, service, mock_git_network):
        """Test restore returns False when stash not found"""
        mock_git_network.run_command.return_value = ""

        result = service.restore_stash("missing")

        assert isinstance(result, ClientSuccess)
        assert result.data is False

    def test_restore_propagates_pop_error(self, service, mock_git_network):
        """Test restore propagates ClientError if pop fails"""
        mock_git_network.run_command.side_effect = [
            "stash@{0}: On main: my-stash\n",     # stash list (found)
            GitCommandError("conflict during pop"), # stash pop fails
        ]

        result = service.restore_stash("my-stash")

        assert isinstance(result, ClientError)
        assert result.error_code == "STASH_POP_ERROR"
