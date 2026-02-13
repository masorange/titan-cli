# plugins/titan-plugin-github/titan_plugin_github/clients/network/gh_network.py
"""
GitHub REST Network Client

Low-level gh CLI command executor.
Handles subprocess execution, authentication, and error handling.
No model conversion - returns raw JSON strings/dicts.
"""
import subprocess
from typing import List, Optional

from ...exceptions import GitHubError, GitHubAuthenticationError, GitHubAPIError
from ...messages import msg


class GHNetwork:
    """
    GitHub REST network client using gh CLI.

    Executes gh CLI commands and handles errors.
    Returns raw command output (strings) without parsing or model conversion.

    Examples:
        >>> network = GHNetwork(repo_owner="acme", repo_name="project")
        >>> output = network.run_command(["pr", "view", "123", "--json", "title"])
        >>> # Returns raw JSON string
    """

    def __init__(self, repo_owner: str, repo_name: str):
        """
        Initialize GH network client.

        Args:
            repo_owner: GitHub repository owner
            repo_name: GitHub repository name

        Raises:
            GitHubAuthenticationError: If gh CLI is not authenticated
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.check_auth()

    def check_auth(self) -> None:
        """
        Check if gh CLI is authenticated.

        Raises:
            GitHubAuthenticationError: If not authenticated
        """
        try:
            subprocess.run(["gh", "auth", "status"], capture_output=True, check=True)
        except subprocess.CalledProcessError:
            raise GitHubAuthenticationError(msg.GitHub.NOT_AUTHENTICATED)

    def run_command(
        self, args: List[str], stdin_input: Optional[str] = None
    ) -> str:
        """
        Run gh CLI command and return stdout.

        Args:
            args: Command arguments (without 'gh' prefix)
            stdin_input: Optional input to pass via stdin (for multiline text)

        Returns:
            Command stdout as string

        Raises:
            GitHubAPIError: If command fails
            GitHubError: If gh CLI not found or unexpected error

        Examples:
            >>> output = network.run_command(["pr", "view", "123", "--json", "title"])
            >>> # Returns: '{"title": "My PR"}'
        """
        try:
            result = subprocess.run(
                ["gh"] + args,
                input=stdin_input,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            raise GitHubAPIError(msg.GitHub.API_ERROR.format(error_msg=error_msg))
        except FileNotFoundError:
            raise GitHubError(msg.GitHub.CLI_NOT_FOUND)
        except Exception as e:
            raise GitHubError(msg.GitHub.UNEXPECTED_ERROR.format(error=e))

    def get_repo_arg(self) -> List[str]:
        """
        Get --repo argument for gh commands.

        Returns:
            List with --repo flag and value, or empty list if no repo configured
        """
        if self.repo_owner and self.repo_name:
            return ["--repo", f"{self.repo_owner}/{self.repo_name}"]
        return []

    def get_repo_string(self) -> str:
        """
        Get repo string in format 'owner/repo'.

        Returns:
            Repository identifier string
        """
        return f"{self.repo_owner}/{self.repo_name}"
