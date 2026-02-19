"""
Unit tests for Tag Service
"""

import pytest
from unittest.mock import Mock
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_git.clients.services.tag_service import TagService
from titan_plugin_git.exceptions import GitCommandError


@pytest.fixture
def mock_git_network():
    """Mock GitNetwork instance"""
    return Mock()


@pytest.fixture
def service(mock_git_network):
    return TagService(mock_git_network)


@pytest.mark.unit
class TestTagServiceCreateTag:
    """Test TagService.create_tag()"""

    def test_create_annotated_tag_at_head(self, service, mock_git_network):
        """Test creates annotated tag at HEAD"""
        mock_git_network.run_command.return_value = ""

        result = service.create_tag("v1.0.0", "Release 1.0.0")

        assert isinstance(result, ClientSuccess)
        mock_git_network.run_command.assert_called_once_with(
            ["git", "tag", "-a", "v1.0.0", "-m", "Release 1.0.0", "HEAD"]
        )

    def test_create_tag_at_specific_ref(self, service, mock_git_network):
        """Test creates tag at specific commit ref"""
        mock_git_network.run_command.return_value = ""

        service.create_tag("v1.0.0", "Release", ref="abc123")

        args = mock_git_network.run_command.call_args.args[0]
        assert "abc123" in args

    def test_create_tag_error_returns_client_error(self, service, mock_git_network):
        """Test git error returns ClientError"""
        mock_git_network.run_command.side_effect = GitCommandError("tag already exists")

        result = service.create_tag("v1.0.0", "msg")

        assert isinstance(result, ClientError)
        assert result.error_code == "TAG_CREATE_ERROR"
        assert "tag already exists" in result.error_message


@pytest.mark.unit
class TestTagServiceDeleteTag:
    """Test TagService.delete_tag()"""

    def test_delete_tag(self, service, mock_git_network):
        """Test deletes local tag"""
        mock_git_network.run_command.return_value = ""

        result = service.delete_tag("v1.0.0")

        assert isinstance(result, ClientSuccess)
        mock_git_network.run_command.assert_called_once_with(
            ["git", "tag", "-d", "v1.0.0"]
        )

    def test_delete_tag_error_returns_client_error(self, service, mock_git_network):
        """Test git error returns ClientError"""
        mock_git_network.run_command.side_effect = GitCommandError("tag not found")

        result = service.delete_tag("v9.9.9")

        assert isinstance(result, ClientError)
        assert result.error_code == "TAG_DELETE_ERROR"


@pytest.mark.unit
class TestTagServiceTagExists:
    """Test TagService.tag_exists()"""

    def test_tag_exists_returns_true(self, service, mock_git_network):
        """Test returns True when tag output matches name"""
        mock_git_network.run_command.return_value = "v1.0.0"

        result = service.tag_exists("v1.0.0")

        assert isinstance(result, ClientSuccess)
        assert result.data is True

    def test_tag_not_exists_returns_false(self, service, mock_git_network):
        """Test returns False when output is empty"""
        mock_git_network.run_command.return_value = ""

        result = service.tag_exists("v9.9.9")

        assert isinstance(result, ClientSuccess)
        assert result.data is False

    def test_error_returns_client_error(self, service, mock_git_network):
        """Test git error returns ClientError"""
        mock_git_network.run_command.side_effect = GitCommandError("not a git repo")

        result = service.tag_exists("v1.0.0")

        assert isinstance(result, ClientError)
        assert result.error_code == "TAG_CHECK_ERROR"


@pytest.mark.unit
class TestTagServiceListTags:
    """Test TagService.list_tags()"""

    def test_list_tags_returns_ui_models(self, service, mock_git_network):
        """Test parses tag names and maps to UIGitTag models"""
        mock_git_network.run_command.return_value = "v1.0.0\nv1.1.0\nv2.0.0\n"

        result = service.list_tags()

        assert isinstance(result, ClientSuccess)
        assert len(result.data) == 3
        tag_names = [t.name for t in result.data]
        assert "v1.0.0" in tag_names
        assert "v2.0.0" in tag_names

    def test_empty_repo_returns_empty_list(self, service, mock_git_network):
        """Test empty output returns empty list"""
        mock_git_network.run_command.return_value = ""

        result = service.list_tags()

        assert isinstance(result, ClientSuccess)
        assert result.data == []

    def test_error_returns_client_error(self, service, mock_git_network):
        """Test git error returns ClientError"""
        mock_git_network.run_command.side_effect = GitCommandError("not a git repo")

        result = service.list_tags()

        assert isinstance(result, ClientError)
        assert result.error_code == "TAG_LIST_ERROR"
