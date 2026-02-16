# plugins/titan-plugin-github/titan_plugin_github/clients/services/pr_service.py
"""
Pull Request Service

Business logic for PR operations.
Uses network layer to fetch data, parses to network models, maps to view models.
"""
import json
import re
from typing import List, Optional, Dict, Any

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network import GHNetwork
from ...models.network.rest import NetworkPullRequest, NetworkPRMergeResult
from ...models.view import UIPullRequest, UIPRMergeResult
from ...models.mappers import from_rest_pr, from_network_pr_merge_result
from ...exceptions import GitHubAPIError
from ...messages import msg


class PRService:
    """
    Service for pull request operations.

    Handles fetching, creating, merging, and listing PRs.
    Returns view models ready for UI rendering.
    """

    def __init__(self, gh_network: GHNetwork):
        """
        Initialize PR service.

        Args:
            gh_network: GHNetwork instance for REST operations
        """
        self.gh = gh_network

    def get_pull_request(self, pr_number: int) -> ClientResult[UIPullRequest]:
        """
        Get a pull request by number.

        Args:
            pr_number: PR number

        Returns:
            ClientResult[UIPullRequest]
        """
        try:
            # Define fields to fetch
            fields = [
                "number", "title", "body", "state", "author",
                "baseRefName", "headRefName", "additions", "deletions",
                "changedFiles", "mergeable", "isDraft", "createdAt",
                "updatedAt", "mergedAt", "reviews", "labels",
            ]

            # Fetch from network
            args = [
                "pr", "view", str(pr_number),
                "--json", ",".join(fields),
            ] + self.gh.get_repo_arg()

            output = self.gh.run_command(args)
            data = json.loads(output)

            # Parse to network model
            rest_pr = NetworkPullRequest.from_json(data)

            # Map to view model
            ui_pr = from_rest_pr(rest_pr)

            return ClientSuccess(data=ui_pr, message=f"PR #{pr_number} retrieved")

        except json.JSONDecodeError as e:
            return ClientError(
                error_message=f"Failed to parse PR data: {e}",
                error_code="JSON_PARSE_ERROR"
            )
        except GitHubAPIError as e:
            if "not found" in str(e).lower():
                return ClientError(
                    error_message=msg.GitHub.PR_NOT_FOUND.format(pr_number=pr_number),
                    error_code="PR_NOT_FOUND"
                )
            return ClientError(error_message=str(e), error_code="API_ERROR")

    def list_pending_review_prs(
        self, max_results: int = 50, include_team_reviews: bool = False
    ) -> ClientResult[List[UIPullRequest]]:
        """
        List PRs pending your review.

        Args:
            max_results: Maximum number of results
            include_team_reviews: If True, includes PRs where only your team is requested

        Returns:
            ClientResult[List[UIPullRequest]]
        """
        try:
            # Get current user
            user_output = self.gh.run_command(["api", "user", "--jq", ".login"])
            current_user = user_output.strip()

            # Fetch PRs
            args = [
                "pr", "list",
                "--search", f"review-requested:{current_user}",
                "--state", "open",
                "--limit", str(max_results),
                "--json", "number,title,author,updatedAt,labels,isDraft,reviewRequests",
            ] + self.gh.get_repo_arg()

            output = self.gh.run_command(args)
            all_prs = json.loads(output)

            # Filter if needed
            if not include_team_reviews:
                filtered_prs = []
                for pr_data in all_prs:
                    review_requests = pr_data.get("reviewRequests", [])
                    if any(req and req.get("login") == current_user for req in review_requests):
                        filtered_prs.append(pr_data)
                all_prs = filtered_prs

            # Parse to network models then map to view models
            ui_prs = []
            for pr_data in all_prs:
                rest_pr = NetworkPullRequest.from_json(pr_data)
                ui_pr = from_rest_pr(rest_pr)
                ui_prs.append(ui_pr)

            return ClientSuccess(
                data=ui_prs,
                message=f"Found {len(ui_prs)} PRs pending review"
            )

        except json.JSONDecodeError as e:
            return ClientError(
                error_message=f"Failed to parse PR list: {e}",
                error_code="JSON_PARSE_ERROR"
            )
        except GitHubAPIError as e:
            return ClientError(error_message=str(e), error_code="API_ERROR")

    def list_my_prs(self, state: str = "open", max_results: int = 50) -> ClientResult[List[UIPullRequest]]:
        """
        List your PRs.

        Args:
            state: PR state (open, closed, merged, all)
            max_results: Maximum number of results

        Returns:
            ClientResult[List[UIPullRequest]]
        """
        try:
            # Get current user
            user_output = self.gh.run_command(["api", "user", "--jq", ".login"])
            current_user = user_output.strip()

            # Fetch PRs
            args = [
                "pr", "list",
                "--state", state,
                "--limit", str(max_results),
                "--json", "number,title,author,updatedAt,labels,isDraft,state,headRefName,baseRefName",
            ] + self.gh.get_repo_arg()

            output = self.gh.run_command(args)
            all_prs = json.loads(output)

            # Filter to current user's PRs
            my_prs = [
                pr for pr in all_prs
                if pr.get("author") and pr["author"].get("login") == current_user
            ]

            # Parse and map
            ui_prs = []
            for pr_data in my_prs:
                rest_pr = NetworkPullRequest.from_json(pr_data)
                ui_pr = from_rest_pr(rest_pr)
                ui_prs.append(ui_pr)

            return ClientSuccess(
                data=ui_prs,
                message=f"Found {len(ui_prs)} PRs"
            )

        except json.JSONDecodeError as e:
            return ClientError(
                error_message=f"Failed to parse PR list: {e}",
                error_code="JSON_PARSE_ERROR"
            )
        except GitHubAPIError as e:
            return ClientError(error_message=str(e), error_code="API_ERROR")

    def list_all_prs(self, state: str = "open", max_results: int = 50) -> ClientResult[List[UIPullRequest]]:
        """
        List all PRs in the repository.

        Args:
            state: PR state (open, closed, merged, all)
            max_results: Maximum number of results

        Returns:
            ClientResult[List[UIPullRequest]]
        """
        try:
            args = [
                "pr", "list",
                "--state", state,
                "--limit", str(max_results),
                "--json", "number,title,author,updatedAt,labels,isDraft,state,reviewRequests",
            ] + self.gh.get_repo_arg()

            output = self.gh.run_command(args)
            all_prs = json.loads(output)

            # Parse and map
            ui_prs = []
            for pr_data in all_prs:
                rest_pr = NetworkPullRequest.from_json(pr_data)
                ui_pr = from_rest_pr(rest_pr)
                ui_prs.append(ui_pr)

            return ClientSuccess(
                data=ui_prs,
                message=f"Found {len(ui_prs)} PRs"
            )

        except json.JSONDecodeError as e:
            return ClientError(
                error_message=f"Failed to parse PR list: {e}",
                error_code="JSON_PARSE_ERROR"
            )
        except GitHubAPIError as e:
            return ClientError(error_message=str(e), error_code="API_ERROR")

    def get_pr_diff(self, pr_number: int, file_path: Optional[str] = None) -> ClientResult[str]:
        """
        Get diff for a PR.

        Args:
            pr_number: PR number
            file_path: Optional specific file to get diff for

        Returns:
            ClientResult[str] with diff content
        """
        try:
            args = ["pr", "diff", str(pr_number)] + self.gh.get_repo_arg()

            if file_path:
                args.extend(["--", file_path])

            diff = self.gh.run_command(args)
            return ClientSuccess(data=diff, message=f"PR #{pr_number} diff retrieved")

        except GitHubAPIError as e:
            if "not found" in str(e).lower():
                return ClientError(
                    error_message=msg.GitHub.PR_NOT_FOUND.format(pr_number=pr_number),
                    error_code="PR_NOT_FOUND"
                )
            return ClientError(error_message=str(e), error_code="API_ERROR")

    def get_pr_files(self, pr_number: int) -> ClientResult[List[str]]:
        """
        Get list of changed files in PR.

        Args:
            pr_number: PR number

        Returns:
            ClientResult[List[str]] with file paths
        """
        try:
            args = [
                "pr", "view", str(pr_number),
                "--json", "files",
            ] + self.gh.get_repo_arg()

            output = self.gh.run_command(args)
            data = json.loads(output)

            files = [f["path"] for f in data.get("files", [])]
            return ClientSuccess(
                data=files,
                message=f"Found {len(files)} changed files"
            )

        except json.JSONDecodeError as e:
            return ClientError(
                error_message=f"Failed to parse files: {e}",
                error_code="JSON_PARSE_ERROR"
            )
        except GitHubAPIError as e:
            return ClientError(error_message=str(e), error_code="API_ERROR")

    def checkout_pr(self, pr_number: int) -> ClientResult[str]:
        """
        Checkout a PR locally.

        Args:
            pr_number: PR number

        Returns:
            ClientResult[str] with branch name that was checked out
        """
        try:
            # Get PR to extract branch name
            pr_result = self.get_pull_request(pr_number)

            match pr_result:
                case ClientSuccess(data=ui_pr):
                    # Checkout using gh CLI
                    args = ["pr", "checkout", str(pr_number)] + self.gh.get_repo_arg()
                    self.gh.run_command(args)

                    # Extract head ref from branch_info (format: "head → base")
                    head_ref = ui_pr.branch_info.split(" → ")[0]
                    return ClientSuccess(
                        data=head_ref,
                        message=f"Checked out PR #{pr_number} to branch {head_ref}"
                    )
                case ClientError() as err:
                    return err

        except GitHubAPIError as e:
            if "not found" in str(e).lower():
                return ClientError(
                    error_message=msg.GitHub.PR_NOT_FOUND.format(pr_number=pr_number),
                    error_code="PR_NOT_FOUND"
                )
            return ClientError(error_message=str(e), error_code="API_ERROR")

    def create_pull_request(
        self,
        title: str,
        body: str,
        base: str,
        head: str,
        draft: bool = False,
        assignees: Optional[List[str]] = None,
        reviewers: Optional[List[str]] = None,
        labels: Optional[List[str]] = None,
    ) -> ClientResult[Dict[str, Any]]:
        """
        Create a pull request.

        Args:
            title: PR title
            body: PR description
            base: Base branch
            head: Head branch
            draft: Whether to create as draft
            assignees: List of assignees
            reviewers: List of reviewers
            labels: List of labels

        Returns:
            ClientResult[Dict] with number, url, state
        """
        try:
            args = [
                "pr", "create",
                "--base", base,
                "--head", head,
                "--title", title,
                "--body", body,
            ]

            if draft:
                args.append("--draft")

            if assignees:
                for assignee in assignees:
                    args.extend(["--assignee", assignee])

            if reviewers:
                for reviewer in reviewers:
                    args.extend(["--reviewer", reviewer])

            if labels:
                for label in labels:
                    args.extend(["--label", label])

            args.extend(self.gh.get_repo_arg())

            # Execute and get PR URL
            output = self.gh.run_command(args)
            pr_url = output.strip()

            # Extract PR number from URL
            try:
                pr_number = int(pr_url.split("/")[-1])
            except ValueError:
                return ClientError(
                    error_message=msg.GitHub.FAILED_TO_PARSE_PR_NUMBER.format(url=output),
                    error_code="PARSE_ERROR"
                )

            return ClientSuccess(
                data={
                    "number": pr_number,
                    "url": pr_url,
                    "state": "draft" if draft else "open",
                },
                message=f"PR #{pr_number} created"
            )

        except GitHubAPIError as e:
            return ClientError(error_message=str(e), error_code="API_ERROR")

    def merge_pr(
        self,
        pr_number: int,
        merge_method: str = "squash",
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> ClientResult[UIPRMergeResult]:
        """
        Merge a pull request.

        Args:
            pr_number: PR number
            merge_method: Merge method (squash, merge, rebase)
            commit_title: Optional commit title
            commit_message: Optional commit message

        Returns:
            ClientResult[UIPRMergeResult]
        """
        try:
            # Validate merge method
            valid_methods = ["squash", "merge", "rebase"]
            if merge_method not in valid_methods:
                network_result = NetworkPRMergeResult(
                    merged=False,
                    message=msg.GitHub.INVALID_MERGE_METHOD.format(
                        method=merge_method, valid_methods=", ".join(valid_methods)
                    ),
                )
                ui_result = from_network_pr_merge_result(network_result)
                return ClientSuccess(data=ui_result, message="Invalid merge method")

            # Build command
            args = ["pr", "merge", str(pr_number), f"--{merge_method}"]

            if commit_title:
                args.extend(["--subject", commit_title])

            if commit_message:
                args.extend(["--body", commit_message])

            args.extend(self.gh.get_repo_arg())

            # Execute merge
            result = self.gh.run_command(args)

            # Extract SHA from output
            sha = None
            if result:
                sha_match = re.search(r"\(([a-f0-9]{7,40})\)", result)
                if sha_match:
                    sha = sha_match.group(1)

            network_result = NetworkPRMergeResult(
                merged=True,
                sha=sha,
                message="Successfully merged"
            )
            ui_result = from_network_pr_merge_result(network_result)
            return ClientSuccess(data=ui_result, message=f"PR #{pr_number} merged")

        except GitHubAPIError as e:
            network_result = NetworkPRMergeResult(merged=False, message=str(e))
            ui_result = from_network_pr_merge_result(network_result)
            return ClientSuccess(data=ui_result, message="Merge failed")

    def add_comment(self, pr_number: int, body: str) -> ClientResult[None]:
        """
        Add a comment to a PR.

        Args:
            pr_number: PR number
            body: Comment text

        Returns:
            ClientResult[None]
        """
        try:
            args = [
                "pr", "comment", str(pr_number),
                "--body", body,
            ] + self.gh.get_repo_arg()

            self.gh.run_command(args)
            return ClientSuccess(data=None, message=f"Comment added to PR #{pr_number}")

        except GitHubAPIError as e:
            if "not found" in str(e).lower():
                return ClientError(
                    error_message=msg.GitHub.PR_NOT_FOUND.format(pr_number=pr_number),
                    error_code="PR_NOT_FOUND"
                )
            return ClientError(error_message=str(e), error_code="API_ERROR")

    def get_pr_commit_sha(self, pr_number: int) -> ClientResult[str]:
        """
        Get the latest commit SHA for a PR.

        Args:
            pr_number: PR number

        Returns:
            ClientResult[str] with latest commit SHA
        """
        try:
            args = [
                "pr", "view", str(pr_number),
                "--json", "commits",
            ] + self.gh.get_repo_arg()

            output = self.gh.run_command(args)
            data = json.loads(output)
            commits = data.get("commits", [])

            if not commits:
                return ClientError(
                    error_message=f"No commits found for PR #{pr_number}",
                    error_code="NO_COMMITS"
                )

            sha = commits[-1]["oid"]
            return ClientSuccess(data=sha, message="Latest commit SHA retrieved")

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            return ClientError(
                error_message=f"Failed to get commit SHA: {e}",
                error_code="PARSE_ERROR"
            )
        except GitHubAPIError as e:
            return ClientError(error_message=str(e), error_code="API_ERROR")
