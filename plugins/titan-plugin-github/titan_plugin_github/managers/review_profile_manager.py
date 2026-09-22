"""Review profile manager for GitHub review workflows."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError
from titan_cli.core.logging import get_logger

from ..models.review_profile_models import ReviewProfile
from ..operations.review_config_merge_operations import (
    ReviewConfigMergeReport,
    merge_review_profile_data,
)
from ..review_profiles import DEFAULT_REVIEW_PROFILE


logger = get_logger(__name__)


@dataclass(frozen=True)
class ReviewProfileResolution:
    """The effective profile plus where it came from and what the project changed."""

    profile: ReviewProfile
    source: str
    path: Optional[Path] = None
    report: ReviewConfigMergeReport = ReviewConfigMergeReport()


class ReviewProfileManager:
    """Resolve the effective review profile for the current project."""

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root

    def get_effective_profile(self) -> ReviewProfile:
        """Return the effective profile: Titan's defaults with the project's on top."""
        return self.resolve().profile

    def resolve(self) -> ReviewProfileResolution:
        """Resolve the profile and report what the project's file changed.

        A project file is merged onto Titan's defaults **per key**, never validated on
        its own: validating it alone let a file that defined one scoring rule silently
        wipe `file_roles`, `change_patterns` and `review_axes`, because every field
        defaults to empty. The result was a review where every file classified as
        "other" and the axes fell back to two — a team that tuned its review got a
        degraded one and nothing said so.
        """
        config_path = self._profile_path()
        if not config_path or not config_path.exists():
            profile = DEFAULT_REVIEW_PROFILE.model_copy(deep=True)
            self._log_resolution(profile, "default", config_path, ReviewConfigMergeReport())
            return ReviewProfileResolution(profile=profile, source="default", path=config_path)

        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid review profile YAML at {config_path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError(
                f"Invalid review profile configuration at {config_path}: "
                f"expected a mapping, got {type(data).__name__}"
            )

        # mode="json" so enum-keyed fields (review_axes) come out as plain strings the
        # YAML can be compared against key-for-key; validation coerces them back.
        base = DEFAULT_REVIEW_PROFILE.model_dump(mode="json")
        merged, report = merge_review_profile_data(base, data)

        try:
            profile = ReviewProfile.model_validate(merged)
        except ValidationError as exc:
            raise ValueError(f"Invalid review profile configuration at {config_path}: {exc}") from exc

        self._log_resolution(profile, "project", config_path, report)
        if report.has_warnings:
            # A `remove:` target that matched nothing, or a misspelled field, changes
            # nothing while looking like it did - fail-open but never in silence.
            logger.warning(
                "review_profile_merge_warnings",
                path=str(config_path),
                unknown_removals=report.unknown_removals,
                ignored_keys=report.ignored_keys,
            )
        return ReviewProfileResolution(
            profile=profile, source="project", path=config_path, report=report
        )

    def _log_resolution(
        self,
        profile: ReviewProfile,
        source: str,
        path: Optional[Path],
        report: ReviewConfigMergeReport,
    ) -> None:
        logger.debug(
            "review_profile_resolved",
            source=source,
            path=str(path) if path else None,
            change_patterns=sorted(profile.change_patterns.keys()),
            file_roles=sorted(profile.file_roles.keys()),
            candidate_scoring_rules=[rule.name for rule in profile.candidate_scoring],
            review_axes=sorted(str(axis) for axis in profile.review_axes.keys()),
            **report.as_log_fields(),
        )

    def _profile_path(self) -> Path | None:
        if not self.project_root:
            return None
        return self.project_root / ".titan" / "review" / "profile.yaml"
