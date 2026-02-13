# plugins/titan-plugin-github/titan_plugin_github/clients/services/issue_service.py
"""
Issue Service

Business logic for issue operations.
Uses REST API for issue operations.
"""
import json
from typing import List, Optional

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
    ) -> UIIssue:
        """
        Create a new GitHub issue.

        Args:
            title: Issue title
            body: Issue description
            assignees: List of assignees
            labels: List of labels

        Returns:
            UIIssue object
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
            issue_number = int(issue_url.split("/")[-1])

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

            return ui_issue

        except (ValueError, json.JSONDecodeError) as e:
            raise GitHubAPIError(f"Failed to create or parse issue: {e}")

    def list_labels(self) -> List[str]:
        """
        List all labels in the repository.

        Returns:
            List of label names
        """
        try:
            args = ["label", "list", "--json", "name"] + self.gh.get_repo_arg()
            output = self.gh.run_command(args)
            labels_data = json.loads(output)

            return [label["name"] for label in labels_data]

        except (ValueError, json.JSONDecodeError) as e:
            raise GitHubAPIError(f"Failed to list labels: {e}")
