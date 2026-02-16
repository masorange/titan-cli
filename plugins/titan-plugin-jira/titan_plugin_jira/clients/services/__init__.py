"""
Jira Services (Internal)

Services are PRIVATE to the JiraClient.
They handle data access: Network → Network model → UI model → Result.

NO business logic here (that's in operations/).
"""

from .issue_service import IssueService
from .project_service import ProjectService
from .comment_service import CommentService
from .transition_service import TransitionService
from .metadata_service import MetadataService
from .link_service import LinkService

__all__ = [
    "IssueService",
    "ProjectService",
    "CommentService",
    "TransitionService",
    "MetadataService",
    "LinkService",
]
