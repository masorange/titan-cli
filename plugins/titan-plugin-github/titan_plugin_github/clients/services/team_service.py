# plugins/titan-plugin-github/titan_plugin_github/clients/services/team_service.py
"""
Team Service

Business logic for GitHub team operations.
"""
from typing import List

from ..network import GHNetwork
from ...exceptions import GitHubAPIError


class TeamService:
    """
    Service for GitHub team operations.

    Handles listing team members and team-related operations.
    """

    def __init__(self, gh_network: GHNetwork):
        """
        Initialize team service.

        Args:
            gh_network: GHNetwork instance for REST operations
        """
        self.gh = gh_network

    def list_team_members(self, team_slug: str) -> List[str]:
        """
        List all members of a GitHub team.

        Args:
            team_slug: Team slug in format "org/team-name" (e.g., "my-org/backend-team")

        Returns:
            List of GitHub usernames (logins)

        Raises:
            GitHubAPIError: If team lookup fails

        Examples:
            >>> members = service.list_team_members("my-org/backend-team")
            >>> # Returns: ['user1', 'user2', 'user3']
        """
        try:
            # Parse org and team from slug
            if '/' not in team_slug:
                raise GitHubAPIError(
                    f"Invalid team slug format. Expected 'org/team', got '{team_slug}'"
                )

            org, team = team_slug.split('/', 1)

            # Use gh api to get team members
            args = ["api", f"/orgs/{org}/teams/{team}/members", "--jq", ".[].login"]
            output = self.gh.run_command(args)

            # Parse output (one username per line)
            members = [line.strip() for line in output.strip().split('\n') if line.strip()]
            return members

        except GitHubAPIError as e:
            raise GitHubAPIError(f"Failed to list team members for '{team_slug}': {e}")
