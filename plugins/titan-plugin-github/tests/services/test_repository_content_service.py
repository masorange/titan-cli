"""Tests for RepositoryContentService."""

from unittest.mock import Mock

from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_github.clients.services import RepositoryContentService
from titan_plugin_github.exceptions import GitHubAPIError


def test_list_repository_directory_returns_entries():
    gh_network = Mock()
    gh_network.repo_owner = "test-owner"
    gh_network.repo_name = "test-repo"
    gh_network.run_command.return_value = '[{"name": "feature-a", "type": "dir"}]'

    service = RepositoryContentService(gh_network)
    result = service.list_repository_directory(
        "catalog/entries",
        repo_owner="example-org",
        repo_name="source-repo",
        ref="main",
    )

    assert isinstance(result, ClientSuccess)
    assert result.data == [{"name": "feature-a", "type": "dir"}]
    gh_network.run_command.assert_called_once_with([
        "api",
        "/repos/example-org/source-repo/contents/catalog/entries?ref=main",
    ])


def test_list_repository_directory_returns_error_when_payload_is_file():
    gh_network = Mock()
    gh_network.repo_owner = "test-owner"
    gh_network.repo_name = "test-repo"
    gh_network.run_command.return_value = '{"name": "openapi.yaml", "type": "file"}'

    service = RepositoryContentService(gh_network)
    result = service.list_repository_directory("catalog/entries/feature-a/spec/openapi.yaml")

    assert isinstance(result, ClientError)
    assert result.error_code == "NOT_A_DIRECTORY"


def test_path_exists_returns_false_for_404():
    gh_network = Mock()
    gh_network.repo_owner = "test-owner"
    gh_network.repo_name = "test-repo"
    gh_network.run_command.side_effect = GitHubAPIError("GitHub API error: 404 Not Found")

    service = RepositoryContentService(gh_network)
    result = service.path_exists("catalog/entries/feature-a/spec/openapi.yaml")

    assert isinstance(result, ClientSuccess)
    assert result.data is False


def test_path_exists_returns_error_for_non_404_api_failure():
    gh_network = Mock()
    gh_network.repo_owner = "test-owner"
    gh_network.repo_name = "test-repo"
    gh_network.run_command.side_effect = GitHubAPIError("GitHub API error: 403 Forbidden")

    service = RepositoryContentService(gh_network)
    result = service.path_exists("catalog/entries/feature-a/spec/openapi.yaml")

    assert isinstance(result, ClientError)
    assert result.error_code == "API_ERROR"
