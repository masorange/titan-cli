"""Manager layer for GitHub plugin orchestration concerns."""

from dataclasses import dataclass

from .checklist_manager import ChecklistManager


@dataclass
class GitHubManagers:
    """Container for GitHub plugin managers used during workflow execution."""

    checklist: ChecklistManager


__all__ = ["ChecklistManager", "GitHubManagers"]
