"""
Jira Services (Internal)

Services are PRIVATE to the JiraClient.
They handle data access: Network → REST → UI conversion.

NO business logic here (that's in operations/).
"""

from .issue_service import IssueService
from .project_service import ProjectService
from .comment_service import CommentService

__all__ = [
    "IssueService",
    "ProjectService",
    "CommentService",
]
