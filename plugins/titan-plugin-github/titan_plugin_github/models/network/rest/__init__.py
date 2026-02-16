"""
REST API Network Models

Faithful representations of GitHub REST API responses (gh CLI JSON output).
Field names preserve API conventions (camelCase).
No transformations or computed fields.
"""

from .user import NetworkUser
from .review import NetworkReview
from .pull_request import NetworkPullRequest, NetworkPRSearchResult, NetworkPRMergeResult
from .issue import NetworkIssue

__all__ = [
    "NetworkUser",
    "NetworkReview",
    "NetworkPullRequest",
    "NetworkPRSearchResult",
    "NetworkPRMergeResult",
    "NetworkIssue",
]
