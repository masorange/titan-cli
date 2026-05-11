"""Checklist manager for GitHub review workflows."""

from pathlib import Path

import yaml
from pydantic import ValidationError
from titan_cli.core.logging import get_logger

from ..checklists.defaults import DEFAULT_REVIEW_CHECKLIST
from ..models.review_models import ReviewChecklistItem
from ..models.review_profile_models import ReviewChecklistFile


logger = get_logger(__name__)


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
        config_path = self._checklist_path()
        if not config_path or not config_path.exists():
            checklist = [item.model_copy(deep=True) for item in DEFAULT_REVIEW_CHECKLIST]
            logger.debug(
                "review_checklist_resolved",
                source="default",
                path=str(config_path) if config_path else None,
                items_count=len(checklist),
                item_ids=[str(item.id) for item in checklist],
            )
            return checklist

        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid review checklist YAML at {config_path}: {exc}") from exc

        try:
            checklist_file = ReviewChecklistFile.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Invalid review checklist configuration at {config_path}: {exc}") from exc

        checklist = [
            ReviewChecklistItem(
                id=item.id,
                name=item.name,
                description=item.description,
                relevant_file_patterns=list(item.relevant_file_patterns),
            )
            for item in checklist_file.items
        ]
        logger.debug(
            "review_checklist_resolved",
            source="project",
            path=str(config_path),
            items_count=len(checklist),
            item_ids=[str(item.id) for item in checklist],
        )
        return checklist

    def _checklist_path(self) -> Path | None:
        if not self.project_root:
            return None
        return self.project_root / ".titan" / "review" / "checklist.yaml"
