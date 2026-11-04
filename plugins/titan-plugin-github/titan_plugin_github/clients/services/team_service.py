# plugins/titan-plugin-github/titan_plugin_github/clients/services/team_service.py
"""
Team Service

Business logic for GitHub team operations.
"""
from typing import List

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from titan_cli.core.logging import log_client_operation

from ..network import GHNetwork, GraphQLNetwork, graphql_queries
from ...models.mappers import from_graphql_user_availability
from ...models.network.graphql import GraphQLUser
from ...models.view import UIUserAvailability
from ...exceptions import GitHubAPIError


class TeamService:
    """
    Service for GitHub team operations.

    Handles listing team members and team-related operations.
    """

    def __init__(self, gh_network: GHNetwork, graphql_network: GraphQLNetwork):
        """
        Initialize team service.

        Args:
            gh_network: GHNetwork instance for REST operations
            graphql_network: GraphQLNetwork instance for GraphQL operations
        """
        self.gh = gh_network
        self.graphql = graphql_network

    @log_client_operation()
    def list_team_members(self, team_slug: str) -> ClientResult[List[str]]:
        """
        List all members of a GitHub team.

        Args:
            team_slug: Team slug in format "org/team-name" (e.g., "my-org/backend-team")

        Returns:
            ClientResult[List[str]] with GitHub usernames (logins)

        Examples:
            >>> result = service.list_team_members("my-org/backend-team")
            >>> match result:
            ...     case ClientSuccess(data=members):
            ...         print(members)  # ['user1', 'user2', 'user3']
        """
        try:
            # Parse org and team from slug
            if '/' not in team_slug:
                return ClientError(
                    error_message=f"Invalid team slug format. Expected 'org/team', got '{team_slug}'",
                    error_code="INVALID_TEAM_SLUG",
                    log_level="warning"
                )

            org, team = team_slug.split('/', 1)

            # Use gh api to get team members
            args = ["api", f"/orgs/{org}/teams/{team}/members", "--jq", ".[].login"]
            output = self.gh.run_command(args)

            # Parse output (one username per line)
            members = [line.strip() for line in output.strip().split('\n') if line.strip()]

            return ClientSuccess(
                data=members,
                message=f"Found {len(members)} team members"
            )

        except GitHubAPIError as e:
            return ClientError(
                error_message=f"Failed to list team members for '{team_slug}': {e}",
                error_code="API_ERROR"
            )

    @log_client_operation()
    def get_users_availability(self, logins: List[str]) -> ClientResult[List[UIUserAvailability]]:
        """
        Whether each GitHub user has the "Busy" status set.

        Args:
            logins: GitHub usernames; duplicates are ignored

        Returns:
            ClientResult[List[UIUserAvailability]], in the order given. GitHub rejects the
            whole request when a login does not exist, which is a ClientError.
        """
        unique = list(dict.fromkeys(logins))
        if not unique:
            return ClientSuccess(data=[], message="No users given")

        try:
            response = self.graphql.run_query(
                graphql_queries.get_users_availability_query(len(unique)),
                variables={f"login{i}": login for i, login in enumerate(unique)},
            )
        except GitHubAPIError as e:
            return ClientError(
                error_message=f"Failed to get user availability: {e}",
                error_code="API_ERROR"
            )

        data = response.get("data") or {}
        users = [
            from_graphql_user_availability(GraphQLUser.from_graphql(node))
            for node in (data.get(f"user{i}") for i in range(len(unique)))
            if node
        ]
        return ClientSuccess(data=users, message=f"Got availability of {len(users)} users")
