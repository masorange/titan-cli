# plugins/titan-plugin-github/titan_plugin_github/clients/services/review_service.py
"""
Review Service

Business logic for PR review operations.
Uses GraphQL for complex operations (threads, comments, resolve).
"""
import json
from typing import List, Optional, Dict, Any

from ..network import GHNetwork, GraphQLNetwork, graphql_queries
from ...models.network.rest import RESTReview
from ...models.network.graphql import GraphQLPullRequestReviewThread
from ...models.view import UICommentThread
from ...models.mappers import from_graphql_review_thread
from ...exceptions import GitHubAPIError
from ...messages import msg


class ReviewService:
    """
    Service for PR review operations.

    Handles threads, comments, reviews, and resolutions.
    Uses GraphQL for complex nested data.
    """

    def __init__(self, gh_network: GHNetwork, graphql_network: GraphQLNetwork):
        """
        Initialize review service.

        Args:
            gh_network: GHNetwork instance for REST operations
            graphql_network: GraphQLNetwork instance for GraphQL operations
        """
        self.gh = gh_network
        self.graphql = graphql_network

    def get_pr_review_threads(
        self, pr_number: int, include_resolved: bool = True
    ) -> List[UICommentThread]:
        """
        Get all review threads for a PR.

        Uses GraphQL to fetch structured threads with comments.

        Args:
            pr_number: PR number
            include_resolved: If False, exclude resolved threads

        Returns:
            List of UICommentThread objects ready for UI
        """
        try:
            # Parse owner/repo
            repo_string = self.gh.get_repo_string()
            owner, repo = repo_string.split('/')

            # Execute GraphQL query
            variables = {
                "owner": owner,
                "repo": repo,
                "prNumber": pr_number
            }

            response = self.graphql.run_query(
                graphql_queries.GET_PR_REVIEW_THREADS,
                variables
            )

            # Extract threads from response
            threads_data = (
                response.get("data", {})
                .get("repository", {})
                .get("pullRequest", {})
                .get("reviewThreads", {})
                .get("nodes", [])
            )

            # Parse to network models
            graphql_threads = []
            for thread_data in threads_data:
                # Skip resolved if requested
                if not include_resolved and thread_data.get("isResolved", False):
                    continue

                thread = GraphQLPullRequestReviewThread.from_graphql(thread_data)
                graphql_threads.append(thread)

            # Map to view models
            ui_threads = [from_graphql_review_thread(t) for t in graphql_threads]

            return ui_threads

        except (KeyError, ValueError) as e:
            raise GitHubAPIError(
                msg.GitHub.API_ERROR.format(
                    error_msg=f"Failed to parse review threads: {e}"
                )
            )

    def resolve_review_thread(self, thread_node_id: str) -> None:
        """
        Resolve a review thread.

        Args:
            thread_node_id: GraphQL node ID of the thread
        """
        try:
            variables = {"threadId": thread_node_id}
            self.graphql.run_mutation(
                graphql_queries.RESOLVE_REVIEW_THREAD,
                variables
            )

        except GitHubAPIError as e:
            raise GitHubAPIError(
                msg.GitHub.API_ERROR.format(
                    error_msg=f"Failed to resolve review thread: {e}"
                )
            )

    def get_pr_reviews(self, pr_number: int) -> List[RESTReview]:
        """
        Get all reviews for a PR.

        Args:
            pr_number: PR number

        Returns:
            List of RESTReview objects
        """
        try:
            repo = self.gh.get_repo_string()
            result = self.gh.run_command(
                ["api", f"/repos/{repo}/pulls/{pr_number}/reviews", "--jq", "."]
            )

            reviews_data = json.loads(result)
            return [RESTReview.from_json(r) for r in reviews_data]

        except (json.JSONDecodeError, KeyError) as e:
            raise GitHubAPIError(
                msg.GitHub.API_ERROR.format(
                    error_msg=f"Failed to get PR reviews: {e}"
                )
            )

    def create_draft_review(self, pr_number: int, payload: Dict[str, Any]) -> int:
        """
        Create a draft review on a PR.

        Args:
            pr_number: PR number
            payload: Review payload with commit_id, body, event, comments

        Returns:
            Review ID
        """
        try:
            repo = self.gh.get_repo_string()
            args = [
                "api",
                f"/repos/{repo}/pulls/{pr_number}/reviews",
                "--method", "POST",
                "--input", "-",
            ]

            # Run with JSON payload via stdin
            import subprocess
            result = subprocess.run(
                ["gh"] + args,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                check=True,
            )

            response = json.loads(result.stdout)
            return response["id"]

        except (json.JSONDecodeError, KeyError, subprocess.CalledProcessError) as e:
            raise GitHubAPIError(
                msg.GitHub.API_ERROR.format(
                    error_msg=f"Failed to create draft review: {e}"
                )
            )

    def submit_review(
        self, pr_number: int, review_id: int, event: str, body: str = ""
    ) -> None:
        """
        Submit a review.

        Args:
            pr_number: PR number
            review_id: Review ID
            event: Review event (APPROVE, REQUEST_CHANGES, COMMENT)
            body: Optional review body text
        """
        try:
            repo = self.gh.get_repo_string()
            args = [
                "api",
                f"/repos/{repo}/pulls/{pr_number}/reviews/{review_id}/events",
                "--method", "POST",
                "-f", f"event={event}",
            ]

            if body:
                args.extend(["-f", f"body={body}"])

            self.gh.run_command(args)

        except GitHubAPIError as e:
            raise GitHubAPIError(
                msg.GitHub.API_ERROR.format(
                    error_msg=f"Failed to submit review: {e}"
                )
            )

    def delete_review(self, pr_number: int, review_id: int) -> None:
        """
        Delete a draft review.

        Args:
            pr_number: PR number
            review_id: Review ID
        """
        try:
            repo = self.gh.get_repo_string()
            args = [
                "api",
                f"/repos/{repo}/pulls/{pr_number}/reviews/{review_id}",
                "--method", "DELETE",
            ]

            self.gh.run_command(args)

        except GitHubAPIError as e:
            raise GitHubAPIError(
                msg.GitHub.API_ERROR.format(
                    error_msg=f"Failed to delete review: {e}"
                )
            )

    def reply_to_comment(self, pr_number: int, comment_id: int, body: str) -> None:
        """
        Reply to a PR comment.

        Args:
            pr_number: PR number
            comment_id: Comment ID to reply to
            body: Reply text
        """
        try:
            repo = self.gh.get_repo_string()
            args = [
                "api", "-X", "POST",
                f"/repos/{repo}/pulls/{pr_number}/comments/{comment_id}/replies",
                "-F", "body=-",
            ]

            self.gh.run_command(args, stdin_input=body)

        except GitHubAPIError as e:
            raise GitHubAPIError(
                msg.GitHub.API_ERROR.format(
                    error_msg=f"Failed to reply to comment: {e}"
                )
            )

    def add_issue_comment(self, pr_number: int, body: str) -> None:
        """
        Add a general comment to PR (issue comment).

        Args:
            pr_number: PR number
            body: Comment text
        """
        try:
            repo = self.gh.get_repo_string()
            args = [
                "api", "-X", "POST",
                f"/repos/{repo}/issues/{pr_number}/comments",
                "-F", "body=-",
            ]

            self.gh.run_command(args, stdin_input=body)

        except GitHubAPIError as e:
            raise GitHubAPIError(
                msg.GitHub.API_ERROR.format(
                    error_msg=f"Failed to add comment: {e}"
                )
            )

    def request_pr_review(
        self, pr_number: int, reviewers: Optional[List[str]] = None
    ) -> None:
        """
        Request review (or re-request) on a PR.

        If reviewers is not provided, re-requests from existing reviewers.

        Args:
            pr_number: PR number
            reviewers: List of GitHub usernames to request review from
        """
        try:
            # Parse owner/repo
            repo_string = self.gh.get_repo_string()
            owner, repo = repo_string.split('/')

            # Get PR node ID and existing reviewers if needed
            if reviewers is None:
                variables = {
                    "owner": owner,
                    "repo": repo,
                    "prNumber": pr_number
                }

                response = self.graphql.run_query(
                    graphql_queries.GET_PR_WITH_REVIEWERS,
                    variables
                )

                pr_data = (
                    response.get("data", {})
                    .get("repository", {})
                    .get("pullRequest", {})
                )

                if not pr_data:
                    raise GitHubAPIError(f"PR #{pr_number} not found")

                pr_node_id = pr_data.get("id")

                # Collect existing reviewers
                existing_reviewers = set()
                reviews = pr_data.get("reviews", {}).get("nodes", [])
                for review in reviews:
                    author = review.get("author", {})
                    if author and author.get("login"):
                        existing_reviewers.add(author["login"])

                review_requests = pr_data.get("reviewRequests", {}).get("nodes", [])
                for request in review_requests:
                    requested = request.get("requestedReviewer", {})
                    if requested and requested.get("login"):
                        existing_reviewers.add(requested["login"])

                reviewers = list(existing_reviewers)

                if not reviewers:
                    return
            else:
                # Get PR node ID
                variables = {
                    "owner": owner,
                    "repo": repo,
                    "prNumber": pr_number
                }

                response = self.graphql.run_query(
                    graphql_queries.GET_PR_NODE_ID,
                    variables
                )

                pr_node_id = (
                    response.get("data", {})
                    .get("repository", {})
                    .get("pullRequest", {})
                    .get("id")
                )

                if not pr_node_id:
                    raise GitHubAPIError(f"PR #{pr_number} not found")

            # Convert usernames to user IDs
            user_ids = []
            for username in reviewers:
                user_response = self.graphql.run_query(
                    graphql_queries.GET_USER_ID,
                    {"login": username}
                )

                user_id = user_response.get("data", {}).get("user", {}).get("id")
                if user_id:
                    user_ids.append(user_id)

            if not user_ids:
                return

            # Request reviews
            self.graphql.run_mutation(
                graphql_queries.REQUEST_REVIEWS,
                {"prId": pr_node_id, "userIds": user_ids}
            )

        except GitHubAPIError as e:
            raise GitHubAPIError(
                msg.GitHub.API_ERROR.format(
                    error_msg=f"Failed to request review on PR #{pr_number}: {e}"
                )
            )
