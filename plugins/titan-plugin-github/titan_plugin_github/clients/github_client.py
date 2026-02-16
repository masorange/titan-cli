# plugins/titan-plugin-github/titan_plugin_github/clients/github_client.py
"""
GitHub Client Facade

High-level facade for GitHub operations.
Delegates to specialized services (PRs, reviews, issues, teams).
"""
from typing import List, Optional, Dict, Any
import json

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from titan_cli.core.secrets import SecretManager
from titan_cli.core.plugins.models import GitHubPluginConfig
from titan_plugin_git.clients.git_client import GitClient

from .network import GHNetwork, GraphQLNetwork
from .services import PRService, ReviewService, IssueService, TeamService
from ..models.view import UIPullRequest, UICommentThread, UIIssue, UIPRMergeResult, UIReview


class GitHubClient:
    """
    GitHub client facade.

    Provides a unified interface for all GitHub operations.
    Internally delegates to specialized services.

    This is the public API for the GitHub plugin.

    Examples:
        >>> config = GitHubPluginConfig()
        >>> client = GitHubClient(config, secrets, git_client, "owner", "repo")
        >>> result = client.get_pull_request(123)
        >>> match result:
        ...     case ClientSuccess(data=pr):
        ...         print(pr.title, pr.status_icon)
    """

    def __init__(
        self,
        config: GitHubPluginConfig,
        secrets: SecretManager,
        git_client: GitClient,
        repo_owner: str,
        repo_name: str
    ):
        """
        Initialize GitHub client.

        Args:
            config: GitHub configuration
            secrets: SecretManager instance
            git_client: Initialized GitClient instance
            repo_owner: GitHub repository owner
            repo_name: GitHub repository name

        Raises:
            GitHubAuthenticationError: If gh CLI is not authenticated
        """
        self.config = config
        self.secrets = secrets
        self.git_client = git_client
        self.repo_owner = repo_owner
        self.repo_name = repo_name

        # Initialize network layers
        self._gh_network = GHNetwork(repo_owner, repo_name)
        self._graphql_network = GraphQLNetwork(self._gh_network)

        # Initialize services
        self._pr_service = PRService(self._gh_network)
        self._review_service = ReviewService(self._gh_network, self._graphql_network)
        self._issue_service = IssueService(self._gh_network)
        self._team_service = TeamService(self._gh_network)

    # ============================================================================
    # Pull Request Operations
    # ============================================================================

    def get_pull_request(self, pr_number: int) -> ClientResult[UIPullRequest]:
        """Get a pull request by number."""
        return self._pr_service.get_pull_request(pr_number)

    def list_pending_review_prs(
        self, max_results: int = 50, include_team_reviews: bool = False
    ) -> ClientResult[List[UIPullRequest]]:
        """List PRs pending your review."""
        return self._pr_service.list_pending_review_prs(max_results, include_team_reviews)

    def list_my_prs(
        self, state: str = "open", max_results: int = 50
    ) -> ClientResult[List[UIPullRequest]]:
        """List your PRs."""
        return self._pr_service.list_my_prs(state, max_results)

    def list_all_prs(
        self, state: str = "open", max_results: int = 50
    ) -> ClientResult[List[UIPullRequest]]:
        """List all PRs in the repository."""
        return self._pr_service.list_all_prs(state, max_results)

    def get_pr_diff(
        self, pr_number: int, file_path: Optional[str] = None
    ) -> ClientResult[str]:
        """Get diff for a PR."""
        return self._pr_service.get_pr_diff(pr_number, file_path)

    def get_pr_files(self, pr_number: int) -> ClientResult[List[str]]:
        """Get list of changed files in PR."""
        return self._pr_service.get_pr_files(pr_number)

    def checkout_pr(self, pr_number: int) -> ClientResult[str]:
        """Checkout a PR locally."""
        return self._pr_service.checkout_pr(pr_number)

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
        excluded_reviewers: Optional[List[str]] = None
    ) -> ClientResult[Dict[str, Any]]:
        """
        Create a pull request.

        Note: excluded_reviewers is handled by expanding team reviewers and filtering.
        """
        # Handle team expansion and exclusions
        final_reviewers = []
        if reviewers:
            for reviewer in reviewers:
                # Check if it's a team (format: "org/team")
                if '/' in reviewer:
                    # Expand team to individual members
                    team_result = self._team_service.list_team_members(reviewer)

                    match team_result:
                        case ClientSuccess(data=team_members):
                            # Filter out excluded reviewers
                            if excluded_reviewers:
                                team_members = [m for m in team_members if m not in excluded_reviewers]
                            final_reviewers.extend(team_members)
                        case ClientError() as err:
                            # If team expansion fails, return error
                            return err
                else:
                    # It's a username, add directly if not excluded
                    if not excluded_reviewers or reviewer not in excluded_reviewers:
                        final_reviewers.append(reviewer)

        return self._pr_service.create_pull_request(
            title, body, base, head, draft, assignees, final_reviewers, labels
        )

    def merge_pr(
        self,
        pr_number: int,
        merge_method: str = "squash",
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> ClientResult[UIPRMergeResult]:
        """Merge a pull request."""
        return self._pr_service.merge_pr(pr_number, merge_method, commit_title, commit_message)

    def add_comment(self, pr_number: int, body: str) -> ClientResult[None]:
        """Add a comment to a PR."""
        return self._pr_service.add_comment(pr_number, body)

    def get_pr_commit_sha(self, pr_number: int) -> ClientResult[str]:
        """Get the latest commit SHA for a PR."""
        return self._pr_service.get_pr_commit_sha(pr_number)

    # ============================================================================
    # Review Operations
    # ============================================================================

    def get_pr_review_threads(
        self, pr_number: int, include_resolved: bool = True
    ) -> ClientResult[List[UICommentThread]]:
        """Get all review threads for a PR."""
        return self._review_service.get_pr_review_threads(pr_number, include_resolved)

    def resolve_review_thread(self, thread_node_id: str) -> ClientResult[None]:
        """Resolve a review thread."""
        return self._review_service.resolve_review_thread(thread_node_id)

    def get_pr_reviews(self, pr_number: int) -> ClientResult[List[UIReview]]:
        """Get all reviews for a PR."""
        return self._review_service.get_pr_reviews(pr_number)

    def create_draft_review(
        self, pr_number: int, payload: Dict[str, Any]
    ) -> ClientResult[int]:
        """Create a draft review on a PR."""
        return self._review_service.create_draft_review(pr_number, payload)

    def submit_review(
        self, pr_number: int, review_id: int, event: str, body: str = ""
    ) -> ClientResult[None]:
        """Submit a review."""
        return self._review_service.submit_review(pr_number, review_id, event, body)

    def delete_review(self, pr_number: int, review_id: int) -> ClientResult[None]:
        """Delete a draft review."""
        return self._review_service.delete_review(pr_number, review_id)

    def reply_to_comment(
        self, pr_number: int, comment_id: int, body: str
    ) -> ClientResult[None]:
        """Reply to a PR comment."""
        return self._review_service.reply_to_comment(pr_number, comment_id, body)

    def add_issue_comment(self, pr_number: int, body: str) -> ClientResult[None]:
        """Add a general comment to PR (issue comment)."""
        return self._review_service.add_issue_comment(pr_number, body)

    def request_pr_review(
        self, pr_number: int, reviewers: Optional[List[str]] = None
    ) -> ClientResult[None]:
        """Request review (or re-request) on a PR."""
        return self._review_service.request_pr_review(pr_number, reviewers)

    # ============================================================================
    # Issue Operations
    # ============================================================================

    def create_issue(
        self,
        title: str,
        body: str,
        assignees: Optional[List[str]] = None,
        labels: Optional[List[str]] = None,
    ) -> ClientResult[UIIssue]:
        """Create a new GitHub issue."""
        return self._issue_service.create_issue(title, body, assignees, labels)

    def list_labels(self) -> ClientResult[List[str]]:
        """List all labels in the repository."""
        return self._issue_service.list_labels()

    # ============================================================================
    # Team Operations
    # ============================================================================

    def list_team_members(self, team_slug: str) -> ClientResult[List[str]]:
        """List all members of a GitHub team."""
        return self._team_service.list_team_members(team_slug)

    # ============================================================================
    # Utility Methods
    # ============================================================================

    def get_current_user(self) -> ClientResult[str]:
        """
        Get the currently authenticated GitHub username.

        Returns:
            ClientResult[str] with GitHub username
        """
        try:
            output = self._gh_network.run_command(["api", "user", "-q", ".login"])
            username = output.strip()
            return ClientSuccess(data=username, message="Current user retrieved")
        except Exception as e:
            return ClientError(
                error_message=f"Failed to get current user: {e}",
                error_code="API_ERROR"
            )

    def get_default_branch(self) -> ClientResult[str]:
        """
        Get the default branch for the repository.

        Checks in order:
        1. Project config (.titan/config.toml -> github.default_branch)
        2. GitHub repository default branch (via API)
        3. Fallback to git client's main_branch

        Returns:
            ClientResult[str] with default branch name (e.g., "main", "develop", "master")
        """
        # Try to get from project config first
        if self.config.default_branch:
            return ClientSuccess(
                data=self.config.default_branch,
                message=f"Default branch from config: {self.config.default_branch}"
            )

        # Fallback to GitHub API
        try:
            args = ["repo", "view", "--json", "defaultBranchRef"] + self._gh_network.get_repo_arg()
            output = self._gh_network.run_command(args)
            data = json.loads(output)

            default_branch_ref = data.get("defaultBranchRef", {})
            branch_name = default_branch_ref.get("name")

            if branch_name:
                return ClientSuccess(
                    data=branch_name,
                    message=f"Default branch from GitHub API: {branch_name}"
                )
        except Exception:
            pass

        # Final fallback: use git plugin's main_branch
        fallback_branch = self.git_client.main_branch
        return ClientSuccess(
            data=fallback_branch,
            message=f"Default branch from git client: {fallback_branch}"
        )
