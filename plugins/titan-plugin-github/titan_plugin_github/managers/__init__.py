"""Manager layer for GitHub plugin orchestration concerns."""

from dataclasses import dataclass

from .checklist_manager import ChecklistManager
from .review_profile_manager import ReviewProfileManager


@dataclass
class GitHubManagers:
    """Container for GitHub plugin managers used during workflow execution."""

    checklist: ChecklistManager
    review_profile: ReviewProfileManager


__all__ = ["ChecklistManager", "GitHubManagers", "ReviewProfileManager"]
