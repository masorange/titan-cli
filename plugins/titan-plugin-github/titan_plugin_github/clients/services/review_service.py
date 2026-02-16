# plugins/titan-plugin-github/titan_plugin_github/clients/services/review_service.py
"""
Review Service

Business logic for PR review operations.
Uses GraphQL for complex operations (threads, comments, resolve).
"""
import json
import subprocess
from typing import List, Optional, Dict, Any

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network import GHNetwork, GraphQLNetwork, graphql_queries
from ...models.network.rest import RESTReview
from ...models.network.graphql import GraphQLPullRequestReviewThread
from ...models.view import UICommentThread
from ...models.mappers import from_graphql_review_thread
from ...exceptions import GitHubAPIError


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
    ) -> ClientResult[List[UICommentThread]]:
        """
        Get all review threads for a PR.

        Uses GraphQL to fetch structured threads with comments.

        Args:
            pr_number: PR number
            include_resolved: If False, exclude resolved threads

        Returns:
            ClientResult[List[UICommentThread]]
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

            return ClientSuccess(
                data=ui_threads,
                message=f"Found {len(ui_threads)} review threads"
            )

        except (KeyError, ValueError) as e:
            return ClientError(
                error_message=f"Failed to parse review threads: {e}",
                error_code="PARSE_ERROR"
            )
        except GitHubAPIError as e:
            return ClientError(error_message=str(e), error_code="API_ERROR")

    def resolve_review_thread(self, thread_node_id: str) -> ClientResult[None]:
        """
        Resolve a review thread.

        Args:
            thread_node_id: GraphQL node ID of the thread

        Returns:
            ClientResult[None]
        """
        try:
            variables = {"threadId": thread_node_id}
            self.graphql.run_mutation(
                graphql_queries.RESOLVE_REVIEW_THREAD,
                variables
            )

            return ClientSuccess(data=None, message="Review thread resolved")

        except GitHubAPIError as e:
            return ClientError(
                error_message=f"Failed to resolve review thread: {e}",
                error_code="API_ERROR"
            )

    def get_pr_reviews(self, pr_number: int) -> ClientResult[List[RESTReview]]:
        """
        Get all reviews for a PR.

        Args:
            pr_number: PR number

        Returns:
            ClientResult[List[RESTReview]]
        """
        try:
            repo = self.gh.get_repo_string()
            result = self.gh.run_command(
                ["api", f"/repos/{repo}/pulls/{pr_number}/reviews", "--jq", "."]
            )

            reviews_data = json.loads(result)
            reviews = [RESTReview.from_json(r) for r in reviews_data]

            return ClientSuccess(
                data=reviews,
                message=f"Found {len(reviews)} reviews"
            )

        except (json.JSONDecodeError, KeyError) as e:
            return ClientError(
                error_message=f"Failed to get PR reviews: {e}",
                error_code="PARSE_ERROR"
            )
        except GitHubAPIError as e:
            return ClientError(error_message=str(e), error_code="API_ERROR")

    def create_draft_review(
        self, pr_number: int, payload: Dict[str, Any]
    ) -> ClientResult[int]:
        """
        Create a draft review on a PR.

        Args:
            pr_number: PR number
            payload: Review payload with commit_id, body, event, comments

        Returns:
            ClientResult[int] with review ID
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
            result = subprocess.run(
                ["gh"] + args,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                check=True,
            )

            response = json.loads(result.stdout)
            review_id = response["id"]

            return ClientSuccess(
                data=review_id,
                message=f"Draft review #{review_id} created"
            )

        except (json.JSONDecodeError, KeyError) as e:
            return ClientError(
                error_message=f"Failed to parse review response: {e}",
                error_code="PARSE_ERROR"
            )
        except subprocess.CalledProcessError as e:
            return ClientError(
                error_message=f"Failed to create draft review: {e}",
                error_code="API_ERROR"
            )
        except GitHubAPIError as e:
            return ClientError(error_message=str(e), error_code="API_ERROR")

    def submit_review(
        self, pr_number: int, review_id: int, event: str, body: str = ""
    ) -> ClientResult[None]:
        """
        Submit a review.

        Args:
            pr_number: PR number
            review_id: Review ID
            event: Review event (APPROVE, REQUEST_CHANGES, COMMENT)
            body: Optional review body text

        Returns:
            ClientResult[None]
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

            return ClientSuccess(data=None, message=f"Review #{review_id} submitted")

        except GitHubAPIError as e:
            return ClientError(
                error_message=f"Failed to submit review: {e}",
                error_code="API_ERROR"
            )

    def delete_review(self, pr_number: int, review_id: int) -> ClientResult[None]:
        """
        Delete a draft review.

        Args:
            pr_number: PR number
            review_id: Review ID

        Returns:
            ClientResult[None]
        """
        try:
            repo = self.gh.get_repo_string()
            args = [
                "api",
                f"/repos/{repo}/pulls/{pr_number}/reviews/{review_id}",
                "--method", "DELETE",
            ]

            self.gh.run_command(args)

            return ClientSuccess(data=None, message=f"Review #{review_id} deleted")

        except GitHubAPIError as e:
            return ClientError(
                error_message=f"Failed to delete review: {e}",
                error_code="API_ERROR"
            )

    def reply_to_comment(
        self, pr_number: int, comment_id: int, body: str
    ) -> ClientResult[None]:
        """
        Reply to a PR comment.

        Args:
            pr_number: PR number
            comment_id: Comment ID to reply to
            body: Reply text

        Returns:
            ClientResult[None]
        """
        try:
            repo = self.gh.get_repo_string()
            args = [
                "api", "-X", "POST",
                f"/repos/{repo}/pulls/{pr_number}/comments/{comment_id}/replies",
                "-F", "body=-",
            ]

            self.gh.run_command(args, stdin_input=body)

            return ClientSuccess(data=None, message="Reply posted")

        except GitHubAPIError as e:
            return ClientError(
                error_message=f"Failed to reply to comment: {e}",
                error_code="API_ERROR"
            )

    def add_issue_comment(self, pr_number: int, body: str) -> ClientResult[None]:
        """
        Add a general comment to PR (issue comment).

        Args:
            pr_number: PR number
            body: Comment text

        Returns:
            ClientResult[None]
        """
        try:
            repo = self.gh.get_repo_string()
            args = [
                "api", "-X", "POST",
                f"/repos/{repo}/issues/{pr_number}/comments",
                "-F", "body=-",
            ]

            self.gh.run_command(args, stdin_input=body)

            return ClientSuccess(data=None, message="Comment added")

        except GitHubAPIError as e:
            return ClientError(
                error_message=f"Failed to add comment: {e}",
                error_code="API_ERROR"
            )

    def request_pr_review(
        self, pr_number: int, reviewers: Optional[List[str]] = None
    ) -> ClientResult[None]:
        """
        Request review (or re-request) on a PR.

        If reviewers is not provided, re-requests from existing reviewers.

        Args:
            pr_number: PR number
            reviewers: List of GitHub usernames to request review from

        Returns:
            ClientResult[None]
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
                    return ClientError(
                        error_message=f"PR #{pr_number} not found",
                        error_code="PR_NOT_FOUND"
                    )

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
                    return ClientSuccess(
                        data=None,
                        message="No existing reviewers to re-request"
                    )
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
                    return ClientError(
                        error_message=f"PR #{pr_number} not found",
                        error_code="PR_NOT_FOUND"
                    )

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
                return ClientSuccess(
                    data=None,
                    message="No valid reviewers found"
                )

            # Request reviews
            self.graphql.run_mutation(
                graphql_queries.REQUEST_REVIEWS,
                {"prId": pr_node_id, "userIds": user_ids}
            )

            return ClientSuccess(
                data=None,
                message=f"Review requested from {len(user_ids)} reviewers"
            )

        except GitHubAPIError as e:
            return ClientError(
                error_message=f"Failed to request review on PR #{pr_number}: {e}",
                error_code="API_ERROR"
            )
