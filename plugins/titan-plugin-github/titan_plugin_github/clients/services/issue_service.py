# plugins/titan-plugin-github/titan_plugin_github/clients/services/issue_service.py
"""
Issue Service

Business logic for issue operations.
Uses REST API for issue operations.
"""
import json
from typing import List, Optional

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network import GHNetwork
from ...models.network.rest import RESTIssue
from ...models.view import UIIssue
from ...models.mappers import from_rest_issue
from ...exceptions import GitHubAPIError


class IssueService:
    """
    Service for issue operations.

    Handles creating, listing, and managing issues.
    """

    def __init__(self, gh_network: GHNetwork):
        """
        Initialize issue service.

        Args:
            gh_network: GHNetwork instance for REST operations
        """
        self.gh = gh_network

    def create_issue(
        self,
        title: str,
        body: str,
        assignees: Optional[List[str]] = None,
        labels: Optional[List[str]] = None,
    ) -> ClientResult[UIIssue]:
        """
        Create a new GitHub issue.

        Args:
            title: Issue title
            body: Issue description
            assignees: List of assignees
            labels: List of labels

        Returns:
            ClientResult[UIIssue]
        """
        try:
            args = ["issue", "create", "--title", title, "--body", body]

            if assignees:
                for assignee in assignees:
                    args.extend(["--assignee", assignee])

            if labels:
                for label in labels:
                    args.extend(["--label", label])

            args.extend(self.gh.get_repo_arg())

            output = self.gh.run_command(args)
            issue_url = output.strip()

            # Extract issue number from URL
            try:
                issue_number = int(issue_url.split("/")[-1])
            except ValueError:
                return ClientError(
                    error_message=f"Failed to parse issue number from URL: {issue_url}",
                    error_code="PARSE_ERROR"
                )

            # Fetch full issue data
            issue_args = [
                "issue", "view", str(issue_number),
                "--json", "number,title,body,state,author,labels,createdAt,updatedAt",
            ] + self.gh.get_repo_arg()

            issue_output = self.gh.run_command(issue_args)
            issue_data = json.loads(issue_output)

            # Parse to network model then map to view
            rest_issue = RESTIssue.from_json(issue_data)
            ui_issue = from_rest_issue(rest_issue)

            return ClientSuccess(data=ui_issue, message=f"Issue #{issue_number} created")

        except json.JSONDecodeError as e:
            return ClientError(
                error_message=f"Failed to parse issue data: {e}",
                error_code="JSON_PARSE_ERROR"
            )
        except GitHubAPIError as e:
            return ClientError(error_message=str(e), error_code="API_ERROR")

    def list_labels(self) -> ClientResult[List[str]]:
        """
        List all labels in the repository.

        Returns:
            ClientResult[List[str]] with label names
        """
        try:
            args = ["label", "list", "--json", "name"] + self.gh.get_repo_arg()
            output = self.gh.run_command(args)
            labels_data = json.loads(output)

            labels = [label["name"] for label in labels_data]
            return ClientSuccess(data=labels, message=f"Found {len(labels)} labels")

        except json.JSONDecodeError as e:
            return ClientError(
                error_message=f"Failed to parse labels: {e}",
                error_code="JSON_PARSE_ERROR"
            )
        except GitHubAPIError as e:
            return ClientError(error_message=str(e), error_code="API_ERROR")
