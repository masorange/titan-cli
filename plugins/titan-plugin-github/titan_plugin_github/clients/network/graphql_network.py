# plugins/titan-plugin-github/titan_plugin_github/clients/network/graphql_network.py
"""
GitHub GraphQL Network Client

Low-level GraphQL query/mutation executor.
Handles gh api graphql execution and error handling.
No model conversion - returns raw GraphQL response dicts.
"""
import json
import time
from typing import Dict, Any, Optional

from titan_cli.core.logging.config import get_logger

from ...exceptions import GitHubAPIError
from ...messages import msg


class GraphQLNetwork:
    """
    GitHub GraphQL network client.

    Executes GraphQL queries and mutations via gh CLI.
    Returns raw GraphQL response data without parsing or model conversion.

    Examples:
        >>> network = GraphQLNetwork(gh_network)
        >>> data = network.run_query(query, variables={"number": 123})
        >>> # Returns raw GraphQL response dict
    """

    def __init__(self, gh_network):
        """
        Initialize GraphQL network client.

        Args:
            gh_network: GHNetwork instance for executing gh commands
        """
        self.gh_network = gh_network
        self._logger = get_logger(__name__)

    def run_query(
        self, query: str, variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            GraphQL response data (parsed JSON)

        Raises:
            GitHubAPIError: If query fails

        Examples:
            >>> query = "query($login: String!) { user(login: $login) { name } }"
            >>> data = network.run_query(query, variables={"login": "john"})
            >>> # Returns: {"data": {"user": {"name": "John Doe"}}}
        """
        return self._execute_graphql(query, variables)

    def run_mutation(
        self, mutation: str, variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL mutation.

        Args:
            mutation: GraphQL mutation string
            variables: Mutation variables

        Returns:
            GraphQL response data (parsed JSON)

        Raises:
            GitHubAPIError: If mutation fails

        Examples:
            >>> mutation = "mutation($id: ID!) { resolveReviewThread(input: {threadId: $id}) { ... } }"
            >>> data = network.run_mutation(mutation, variables={"id": "..."})
        """
        return self._execute_graphql(mutation, variables)

    def _execute_graphql(
        self, operation: str, variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL operation (query or mutation).

        Args:
            operation: GraphQL operation string
            variables: Variables for the operation

        Returns:
            Parsed GraphQL response

        Raises:
            GitHubAPIError: If execution fails
        """
        # Detect type from first keyword — never log query content or variables (may contain PR/issue body)
        op_type = "mutation" if operation.lstrip().startswith("mutation") else "query"
        start = time.time()

        try:
            # Build payload as JSON
            payload = {"query": operation}
            if variables:
                payload["variables"] = variables

            # Use --input - to pass JSON via stdin (cleaner than field flags)
            args = ["api", "graphql", "--input", "-"]

            # Execute command with JSON payload via stdin
            output = self.gh_network.run_command(args, stdin_input=json.dumps(payload))

            # Parse JSON response
            response = json.loads(output)

            # Check for GraphQL errors
            if "errors" in response:
                errors = response["errors"]
                error_messages = [e.get("message", str(e)) for e in errors]
                self._logger.debug(
                    "graphql_errors",
                    op_type=op_type,
                    duration=round(time.time() - start, 3),
                )
                raise GitHubAPIError(
                    msg.GitHub.API_ERROR.format(
                        error_msg=f"GraphQL errors: {'; '.join(error_messages)}"
                    )
                )

            self._logger.debug(
                "graphql_ok",
                op_type=op_type,
                duration=round(time.time() - start, 3),
            )
            return response

        except json.JSONDecodeError as e:
            raise GitHubAPIError(
                msg.GitHub.API_ERROR.format(
                    error_msg=f"Failed to parse GraphQL response: {e}"
                )
            )
        except GitHubAPIError:
            # Re-raise GitHubAPIError as-is
            raise
        except Exception as e:
            raise GitHubAPIError(
                msg.GitHub.API_ERROR.format(error_msg=f"GraphQL execution failed: {e}")
            )
