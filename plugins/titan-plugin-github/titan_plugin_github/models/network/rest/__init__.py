"""
REST API Network Models

Faithful representations of GitHub REST API responses (gh CLI JSON output).
Field names preserve API conventions (camelCase).
No transformations or computed fields.
"""

from .user import NetworkUser
from .review import NetworkReview
from .pull_request import NetworkPullRequest, NetworkPRSearchResult, NetworkPRMergeResult, NetworkPRFile, NetworkPRCreated
from .issue import NetworkIssue
from .release import NetworkRelease

__all__ = [
    "NetworkUser",
    "NetworkReview",
    "NetworkPullRequest",
    "NetworkPRSearchResult",
    "NetworkPRMergeResult",
    "NetworkPRFile",
    "NetworkPRCreated",
    "NetworkIssue",
    "NetworkRelease",
]
