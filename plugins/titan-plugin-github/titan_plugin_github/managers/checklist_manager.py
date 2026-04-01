"""Checklist manager for GitHub review workflows."""

from pathlib import Path

from ..checklists.defaults import DEFAULT_REVIEW_CHECKLIST
from ..models.review_models import ReviewChecklistItem


class ChecklistManager:
    """Resolve the effective review checklist for the current project."""

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root

    def get_effective_checklist(self) -> list[ReviewChecklistItem]:
        """
        Return the review checklist to use for the current project.

        The manager currently serves the built-in default checklist. It owns
        future project-specific resolution so the workflow step does not need
        to know where the checklist comes from.
        """
        return [item.model_copy(deep=True) for item in DEFAULT_REVIEW_CHECKLIST]
