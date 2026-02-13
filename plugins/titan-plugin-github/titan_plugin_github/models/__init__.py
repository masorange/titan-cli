"""
GitHub Plugin Models

This package contains data models for the GitHub plugin:
- network.py: Network/API models (GraphQL responses, REST API data)
- view.py: View/UI models (optimized for rendering in widgets)
"""

# Network/API models
from .network import (
    User,
    ReviewComment,
    Review,
    PullRequest,
    PRReviewComment,
    PRReviewThread,
    PRIssueComment,
    PRSearchResult,
    PRMergeResult,
    Issue,
)

# View/UI models
from .view import UIComment, UICommentThread

__all__ = [
    # Network models (from API/GraphQL)
    "User",
    "ReviewComment",
    "Review",
    "PullRequest",
    "PRReviewComment",
    "PRReviewThread",
    "PRIssueComment",
    "PRSearchResult",
    "PRMergeResult",
    "Issue",
    # View models (for UI rendering)
    "UIComment",
    "UICommentThread",
]
