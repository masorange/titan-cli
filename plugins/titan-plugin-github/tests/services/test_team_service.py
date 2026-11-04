"""
Unit tests for TeamService
"""

import pytest
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_github.clients.services.team_service import TeamService
from titan_plugin_github.exceptions import GitHubAPIError


@pytest.fixture
def team_service(mock_gh_network, mock_graphql_network):
    return TeamService(mock_gh_network, mock_graphql_network)


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


@pytest.mark.unit
class TestTeamServiceGetUsersAvailability:
    """Test TeamService.get_users_availability()"""

    def test_maps_busy_and_available(self, team_service, mock_graphql_network):
        mock_graphql_network.run_query.return_value = {"data": {
            "user0": {"login": "a", "status": {"indicatesLimitedAvailability": True, "message": "Vacaciones"}},
            "user1": {"login": "b", "status": None},
        }}

        result = team_service.get_users_availability(["a", "b"])

        assert isinstance(result, ClientSuccess)
        assert [(u.login, u.is_busy, u.status_message) for u in result.data] == [
            ("a", True, "Vacaciones"),
            ("b", False, ""),
        ]

    def test_logins_travel_as_variables_not_in_the_query(self, team_service, mock_graphql_network):
        mock_graphql_network.run_query.return_value = {"data": {"user0": None}}

        team_service.get_users_availability(["evil\") { x }", "evil\") { x }"])

        query = mock_graphql_network.run_query.call_args.args[0]
        variables = mock_graphql_network.run_query.call_args.kwargs["variables"]
        assert "evil" not in query
        assert variables == {"login0": "evil\") { x }"}

    def test_no_logins_makes_no_call(self, team_service, mock_graphql_network):
        result = team_service.get_users_availability([])

        assert isinstance(result, ClientSuccess) and result.data == []
        mock_graphql_network.run_query.assert_not_called()

    def test_api_error_returns_client_error(self, team_service, mock_graphql_network):
        mock_graphql_network.run_query.side_effect = GitHubAPIError("boom")

        result = team_service.get_users_availability(["a"])

        assert isinstance(result, ClientError)
        assert result.error_code == "API_ERROR"
