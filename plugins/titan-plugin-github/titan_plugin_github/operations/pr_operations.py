"""
Pull Request Operations

Pure business logic for PR-related operations.
No UI dependencies - all functions can be unit tested.
"""

from typing import List
from titan_cli.core.result import ClientSuccess, ClientError
from ..models.view import UICommentThread


def fetch_pr_threads(
    github_client,
    pr_number: int,
    include_resolved: bool = False
) -> List[UICommentThread]:
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
        List of filtered UICommentThread objects (view models)

    Raises:
        Exception: If fetching threads fails

    Example:
        >>> threads = fetch_pr_threads(github, 123, include_resolved=False)
        >>> len(threads)
        5
        >>> all(not t.is_resolved for t in threads)
        True
    """
    # Fetch all threads using GraphQL
    result = github_client.get_pr_review_threads(
        pr_number,
        include_resolved=include_resolved
    )

    # Handle ClientResult
    match result:
        case ClientSuccess(data=threads):
            all_threads = threads
        case ClientError(error_message=err):
            raise Exception(f"Failed to fetch threads: {err}")
        case _:
            raise Exception("Unexpected result type")

    # Filter out unwanted threads
    filtered_threads = []

    for thread in all_threads:
        main_comment = thread.main_comment
        if not main_comment:
            continue

        # Skip bot comments
        if main_comment.author_login and 'bot' in main_comment.author_login.lower():
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
