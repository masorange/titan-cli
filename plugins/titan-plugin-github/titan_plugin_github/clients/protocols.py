# plugins/titan-plugin-github/titan_plugin_github/clients/protocols.py
"""
GitHub Client Protocols

Protocols (interfaces) for GitHub network operations.
Used for type checking and easy mocking in tests.
"""
from typing import Protocol, List, Dict, Any, Optional


class GitHubNetworkProtocol(Protocol):
    """
    Protocol for GitHub REST network operations (gh CLI).

    Defines the interface for executing gh CLI commands.
    Implementations handle subprocess execution and error handling.
    """

    def run_command(
        self, args: List[str], stdin_input: Optional[str] = None
    ) -> str:
        """
        Run gh CLI command and return stdout.

        Args:
            args: Command arguments (without 'gh' prefix)
            stdin_input: Optional input to pass via stdin

        Returns:
            Command stdout as string

        Raises:
            GitHubAPIError: If command fails
        """
        ...

    def check_auth(self) -> None:
        """
        Check if gh CLI is authenticated.

        Raises:
            GitHubAuthenticationError: If not authenticated
        """
        ...


class GitHubGraphQLProtocol(Protocol):
    """
    Protocol for GitHub GraphQL network operations.

    Defines the interface for executing GraphQL queries and mutations.
    """

    def run_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            GraphQL response data

        Raises:
            GitHubAPIError: If query fails
        """
        ...

    def run_mutation(
        self, mutation: str, variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL mutation.

        Args:
            mutation: GraphQL mutation string
            variables: Mutation variables

        Returns:
            GraphQL response data

        Raises:
            GitHubAPIError: If mutation fails
        """
        ...
