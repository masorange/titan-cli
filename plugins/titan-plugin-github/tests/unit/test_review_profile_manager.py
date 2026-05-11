from pathlib import Path

import pytest

from titan_plugin_github.managers.review_profile_manager import ReviewProfileManager
from titan_plugin_github.review_profiles import DEFAULT_REVIEW_PROFILE


def test_returns_default_profile_when_file_missing():
    profile = ReviewProfileManager().get_effective_profile()

    assert profile == DEFAULT_REVIEW_PROFILE
    assert profile is not DEFAULT_REVIEW_PROFILE


def test_loads_project_profile_from_yaml(tmp_path: Path):
    review_dir = tmp_path / ".titan" / "review"
    review_dir.mkdir(parents=True)
    (review_dir / "profile.yaml").write_text(
        """
version: 1
change_patterns:
  central_behavior:
    - "**/core/**"
file_roles:
  tests:
    - "**/tests/**"
candidate_scoring:
  - name: security_sensitive
    patterns:
      - "**/auth/**"
    score_delta: 5
    reason: security or access-sensitive area
candidate_exclusions:
  low_signal_test_max_changes: 5
  low_signal_config_max_changes: 3
review_axes:
  functional_correctness:
    always_include: true
  security:
    patterns:
      - "**/auth/**"
""".strip(),
        encoding="utf-8",
    )

    profile = ReviewProfileManager(project_root=tmp_path).get_effective_profile()

    assert profile.candidate_exclusions.low_signal_test_max_changes == 5
    assert profile.candidate_scoring[0].name == "security_sensitive"
    assert profile.review_axes["security"].patterns == ["**/auth/**"]


def test_invalid_profile_yaml_raises_clear_error(tmp_path: Path):
    review_dir = tmp_path / ".titan" / "review"
    review_dir.mkdir(parents=True)
    (review_dir / "profile.yaml").write_text("candidate_scoring: [", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid review profile YAML"):
        ReviewProfileManager(project_root=tmp_path).get_effective_profile()


def test_invalid_profile_config_raises_clear_error(tmp_path: Path):
    review_dir = tmp_path / ".titan" / "review"
    review_dir.mkdir(parents=True)
    (review_dir / "profile.yaml").write_text(
        """
version: 1
candidate_scoring:
  - name: broken
    patterns:
      - "**/auth/**"
    score_delta: nope
    reason: invalid
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid review profile configuration"):
        ReviewProfileManager(project_root=tmp_path).get_effective_profile()
