"""
Unit tests for Remote Service
"""

import pytest
from unittest.mock import Mock
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_git.clients.services.remote_service import RemoteService
from titan_plugin_git.exceptions import GitCommandError


@pytest.fixture
def mock_git_network():
    """Mock GitNetwork instance"""
    return Mock()


@pytest.fixture
def service(mock_git_network):
    return RemoteService(mock_git_network)


@pytest.mark.unit
class TestRemoteServicePush:
    """Test RemoteService.push()"""

    def test_push_basic(self, service, mock_git_network):
        """Test basic push to remote"""
        mock_git_network.run_command.return_value = ""

        result = service.push(remote="origin")

        assert isinstance(result, ClientSuccess)
        args = mock_git_network.run_command.call_args.args[0]
        assert args == ["git", "push", "origin"]

    def test_push_with_branch(self, service, mock_git_network):
        """Test push with explicit branch name"""
        mock_git_network.run_command.return_value = ""

        service.push(remote="origin", branch="feature")

        args = mock_git_network.run_command.call_args.args[0]
        assert "feature" in args

    def test_push_with_set_upstream(self, service, mock_git_network):
        """Test push with -u flag"""
        mock_git_network.run_command.return_value = ""

        service.push(remote="origin", set_upstream=True)

        args = mock_git_network.run_command.call_args.args[0]
        assert "-u" in args

    def test_push_with_tags(self, service, mock_git_network):
        """Test push with --tags flag"""
        mock_git_network.run_command.return_value = ""

        service.push(remote="origin", tags=True)

        args = mock_git_network.run_command.call_args.args[0]
        assert "--tags" in args

    def test_push_error_returns_client_error(self, service, mock_git_network):
        """Test git error returns ClientError"""
        mock_git_network.run_command.side_effect = GitCommandError("rejected")

        result = service.push()

        assert isinstance(result, ClientError)
        assert result.error_code == "PUSH_ERROR"
        assert "rejected" in result.error_message


@pytest.mark.unit
class TestRemoteServicePull:
    """Test RemoteService.pull()"""

    def test_pull_basic(self, service, mock_git_network):
        """Test basic pull from remote"""
        mock_git_network.run_command.return_value = ""

        result = service.pull(remote="origin")

        assert isinstance(result, ClientSuccess)
        args = mock_git_network.run_command.call_args.args[0]
        assert args == ["git", "pull", "origin"]

    def test_pull_with_branch(self, service, mock_git_network):
        """Test pull with explicit branch"""
        mock_git_network.run_command.return_value = ""

        service.pull(remote="origin", branch="main")

        args = mock_git_network.run_command.call_args.args[0]
        assert "main" in args

    def test_pull_error_returns_client_error(self, service, mock_git_network):
        """Test git error returns ClientError"""
        mock_git_network.run_command.side_effect = GitCommandError("merge conflict")

        result = service.pull()

        assert isinstance(result, ClientError)
        assert result.error_code == "PULL_ERROR"


@pytest.mark.unit
class TestRemoteServiceFetch:
    """Test RemoteService.fetch()"""

    def test_fetch_single_remote(self, service, mock_git_network):
        """Test fetch from specific remote"""
        mock_git_network.run_command.return_value = ""

        result = service.fetch(remote="origin")

        assert isinstance(result, ClientSuccess)
        args = mock_git_network.run_command.call_args.args[0]
        assert args == ["git", "fetch", "origin"]

    def test_fetch_with_branch(self, service, mock_git_network):
        """Test fetch specific branch from remote"""
        mock_git_network.run_command.return_value = ""

        service.fetch(remote="origin", branch="main")

        args = mock_git_network.run_command.call_args.args[0]
        assert args == ["git", "fetch", "origin", "main"]

    def test_fetch_all_remotes(self, service, mock_git_network):
        """Test fetch --all ignores remote and branch args"""
        mock_git_network.run_command.return_value = ""

        service.fetch(all=True)

        args = mock_git_network.run_command.call_args.args[0]
        assert args == ["git", "fetch", "--all"]

    def test_fetch_error_returns_client_error(self, service, mock_git_network):
        """Test git error returns ClientError"""
        mock_git_network.run_command.side_effect = GitCommandError("network error")

        result = service.fetch()

        assert isinstance(result, ClientError)
        assert result.error_code == "FETCH_ERROR"


@pytest.mark.unit
class TestRemoteServiceGetGithubRepoInfo:
    """Test RemoteService.get_github_repo_info()"""

    def test_parses_ssh_url(self, service, mock_git_network):
        """Test parses git@github.com SSH URL"""
        mock_git_network.run_command.return_value = "git@github.com:myorg/myrepo.git\n"

        result = service.get_github_repo_info()

        assert isinstance(result, ClientSuccess)
        owner, name = result.data
        assert owner == "myorg"
        assert name == "myrepo"

    def test_parses_https_url(self, service, mock_git_network):
        """Test parses https://github.com HTTPS URL"""
        mock_git_network.run_command.return_value = "https://github.com/myorg/myrepo.git\n"

        result = service.get_github_repo_info()

        assert isinstance(result, ClientSuccess)
        owner, name = result.data
        assert owner == "myorg"
        assert name == "myrepo"

    def test_non_github_url_returns_none_tuple(self, service, mock_git_network):
        """Test non-GitHub remote returns (None, None)"""
        mock_git_network.run_command.return_value = "git@gitlab.com:myorg/myrepo.git\n"

        result = service.get_github_repo_info()

        assert isinstance(result, ClientSuccess)
        assert result.data == (None, None)

    def test_error_returns_client_error(self, service, mock_git_network):
        """Test git error returns ClientError"""
        mock_git_network.run_command.side_effect = GitCommandError("no remote 'origin'")

        result = service.get_github_repo_info()

        assert isinstance(result, ClientError)
        assert result.error_code == "REMOTE_ERROR"
