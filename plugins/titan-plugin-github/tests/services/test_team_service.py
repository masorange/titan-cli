"""
Unit tests for TeamService
"""

import pytest
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_github.clients.services.team_service import TeamService
from titan_plugin_github.exceptions import GitHubAPIError


@pytest.fixture
def team_service(mock_gh_network):
    return TeamService(mock_gh_network)


@pytest.mark.unit
class TestTeamServiceListTeamMembers:
    """Test TeamService.list_team_members()"""

    def test_returns_member_list(self, team_service, mock_gh_network):
        """Test parses newline-separated usernames into a list"""
        mock_gh_network.run_command.return_value = "user1\nuser2\nuser3\n"

        result = team_service.list_team_members("my-org/backend-team")

        assert isinstance(result, ClientSuccess)
        assert result.data == ["user1", "user2", "user3"]

    def test_calls_correct_api_endpoint(self, team_service, mock_gh_network):
        """Test constructs correct gh api path from org/team slug"""
        mock_gh_network.run_command.return_value = "user1\n"

        team_service.list_team_members("acme-corp/platform")

        args = mock_gh_network.run_command.call_args.args[0]
        assert "/orgs/acme-corp/teams/platform/members" in " ".join(args)

    def test_empty_team_returns_empty_list(self, team_service, mock_gh_network):
        """Test empty output returns empty list"""
        mock_gh_network.run_command.return_value = ""

        result = team_service.list_team_members("my-org/empty-team")

        assert isinstance(result, ClientSuccess)
        assert result.data == []

    def test_invalid_slug_without_slash_returns_error(self, team_service, mock_gh_network):
        """Test slug without org/team separator returns ClientError immediately"""
        result = team_service.list_team_members("no-slash-here")

        assert isinstance(result, ClientError)
        assert result.error_code == "INVALID_TEAM_SLUG"
        mock_gh_network.run_command.assert_not_called()

    def test_api_error_returns_client_error(self, team_service, mock_gh_network):
        """Test GitHub API error returns ClientError"""
        mock_gh_network.run_command.side_effect = GitHubAPIError("team not found")

        result = team_service.list_team_members("my-org/nonexistent")

        assert isinstance(result, ClientError)
        assert result.error_code == "API_ERROR"
        assert "my-org/nonexistent" in result.error_message
