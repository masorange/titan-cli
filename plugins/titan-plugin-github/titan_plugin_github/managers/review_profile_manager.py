"""Review profile manager for GitHub review workflows."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from ..models.review_profile_models import ReviewProfile
from ..review_profiles import DEFAULT_REVIEW_PROFILE


class ReviewProfileManager:
    """Resolve the effective review profile for the current project."""

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root

    def get_effective_profile(self) -> ReviewProfile:
        """Return project review profile or built-in defaults when absent."""
        config_path = self._profile_path()
        if not config_path or not config_path.exists():
            return DEFAULT_REVIEW_PROFILE.model_copy(deep=True)

        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid review profile YAML at {config_path}: {exc}") from exc

        try:
            return ReviewProfile.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Invalid review profile configuration at {config_path}: {exc}") from exc

    def _profile_path(self) -> Path | None:
        if not self.project_root:
            return None
        return self.project_root / ".titan" / "review" / "profile.yaml"
