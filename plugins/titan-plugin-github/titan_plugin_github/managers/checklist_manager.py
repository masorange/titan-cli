"""Checklist manager for GitHub review workflows."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError
from titan_cli.core.logging import get_logger

from ..checklists.defaults import DEFAULT_REVIEW_CHECKLIST
from ..models.review_models import ReviewChecklistItem
from ..models.review_profile_models import ReviewChecklistFile
from ..operations.review_config_merge_operations import (
    REMOVE_KEY,
    ReviewConfigMergeReport,
    merge_review_checklist_items,
)


logger = get_logger(__name__)


@dataclass(frozen=True)
class ReviewChecklistResolution:
    """The effective checklist plus where it came from and what the project changed."""

    checklist: list[ReviewChecklistItem]
    source: str
    path: Optional[Path] = None
    report: ReviewConfigMergeReport = ReviewConfigMergeReport()


class ChecklistManager:
    """Resolve the effective review checklist for the current project."""

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root

    def get_effective_checklist(self) -> list[ReviewChecklistItem]:
        """Return the effective checklist: Titan's twelve with the project's on top."""
        return self.resolve().checklist

    def resolve(self) -> ReviewChecklistResolution:
        """Resolve the checklist and report what the project's file changed.

        Merged by `id` onto Titan's defaults, not substituted for them: a project
        checklist used to REPLACE all twelve, so adding one project-specific item cost
        the other eleven — and nothing on screen distinguished "we wrote one item" from
        "we review one thing".
        """
        config_path = self._checklist_path()
        if not config_path or not config_path.exists():
            checklist = [item.model_copy(deep=True) for item in DEFAULT_REVIEW_CHECKLIST]
            self._log_resolution(checklist, "default", config_path, ReviewConfigMergeReport())
            return ReviewChecklistResolution(
                checklist=checklist, source="default", path=config_path
            )

        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid review checklist YAML at {config_path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError(
                f"Invalid review checklist configuration at {config_path}: "
                f"expected a mapping, got {type(data).__name__}"
            )

        removals = data.get(REMOVE_KEY)
        base_items = [item.model_dump(mode="json") for item in DEFAULT_REVIEW_CHECKLIST]
        project_items = data.get("items") or []
        if not isinstance(project_items, list):
            raise ValueError(
                f"Invalid review checklist configuration at {config_path}: "
                f"'items' must be a list, got {type(project_items).__name__}"
            )

        merged_items, report = merge_review_checklist_items(base_items, project_items, removals)

        try:
            checklist_file = ReviewChecklistFile.model_validate(
                {"version": data.get("version", 1), "items": merged_items}
            )
        except ValidationError as exc:
            raise ValueError(f"Invalid review checklist configuration at {config_path}: {exc}") from exc

        checklist = [
            ReviewChecklistItem(
                id=item.id,
                name=item.name,
                description=item.description,
            )
            for item in checklist_file.items
        ]
        self._log_resolution(checklist, "project", config_path, report)
        if report.has_warnings:
            logger.warning(
                "review_checklist_merge_warnings",
                path=str(config_path),
                unknown_removals=report.unknown_removals,
                ignored_keys=report.ignored_keys,
            )
        return ReviewChecklistResolution(
            checklist=checklist, source="project", path=config_path, report=report
        )

    def _log_resolution(
        self,
        checklist: list[ReviewChecklistItem],
        source: str,
        path: Optional[Path],
        report: ReviewConfigMergeReport,
    ) -> None:
        logger.info(
            "review_checklist_resolved",
            source=source,
            path=str(path) if path else None,
            items_count=len(checklist),
            item_ids=[str(item.id) for item in checklist],
            **report.as_log_fields(),
        )

    def _checklist_path(self) -> Path | None:
        if not self.project_root:
            return None
        return self.project_root / ".titan" / "review" / "checklist.yaml"
