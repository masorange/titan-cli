"""
Pull Request Operations

Pure business logic for PR-related operations.
No UI dependencies - all functions can be unit tested.
"""

from typing import List
from ..models.network.graphql import GraphQLPullRequestReviewThread


def fetch_pr_threads(
    github_client,
    pr_number: int,
    include_resolved: bool = False
) -> List[GraphQLPullRequestReviewThread]:
    """
    Fetch and filter PR review threads.

    Filters out:
    - Bot comments
    - Empty comments
    - JSON-only comments (coverage reports, etc.)
    - Resolved threads (if include_resolved=False)

    Args:
        github_client: GitHub client instance
        pr_number: PR number
        include_resolved: Whether to include resolved threads

    Returns:
        List of filtered GraphQLPullRequestReviewThread objects

    Example:
        >>> threads = fetch_pr_threads(github, 123, include_resolved=False)
        >>> len(threads)
        5
        >>> all(not t.is_resolved for t in threads)
        True
    """
    # Fetch all threads using GraphQL
    all_threads = github_client.get_pr_review_threads(
        pr_number,
        include_resolved=include_resolved
    )

    # Filter out unwanted threads
    filtered_threads = []

    for thread in all_threads:
        main_comment = thread.main_comment
        if not main_comment:
            continue

        # Skip bot comments
        if main_comment.author and 'bot' in main_comment.author.login.lower():
            continue

        # Skip empty comments
        if not main_comment.body or not main_comment.body.strip():
            continue

        # Skip JSON-only comments (coverage reports, etc.)
        body_stripped = main_comment.body.strip()
        if body_stripped.startswith('{') and body_stripped.endswith('}'):
            continue

        filtered_threads.append(thread)

    return filtered_threads


def push_and_request_review(
    github_client,
    git_client,
    worktree_path: str,
    branch: str,
    pr_number: int,
    remote: str = "origin"
) -> bool:
    """
    Push commits from worktree and re-request review.

    Args:
        github_client: GitHub client
        git_client: Git client
        worktree_path: Path to worktree
        branch: Branch name to push
        pr_number: PR number
        remote: Git remote name (default: "origin")

    Returns:
        True if successful, False otherwise

    Example:
        >>> success = push_and_request_review(
        ...     github, git, "/tmp/worktree",
        ...     "feature-branch", 123
        ... )
        >>> success
        True
    """
    try:
        # Push from worktree
        git_client.run_in_worktree(
            worktree_path,
            ["git", "push", remote, branch]
        )

        # Re-request review from existing reviewers
        github_client.request_pr_review(pr_number)

        return True

    except Exception:
        return False
