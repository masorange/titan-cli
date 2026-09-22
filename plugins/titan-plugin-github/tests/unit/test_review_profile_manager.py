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
    assert profile.review_axes["security"].patterns == ["**/auth/**"]

    # The project's rule REPLACES Titan's rule of the same name in place, so the
    # default order survives instead of the project's four-line file becoming the
    # whole of the scoring policy.
    by_name = {rule.name: rule for rule in profile.candidate_scoring}
    assert by_name["security_sensitive"].patterns == ["**/auth/**"]
    assert "domain_critical_path" in by_name
    assert "shared_helper" in by_name


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


def _write_profile(tmp_path: Path, body: str) -> None:
    review_dir = tmp_path / ".titan" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "profile.yaml").write_text(body.strip(), encoding="utf-8")


def test_a_partial_project_profile_no_longer_wipes_the_defaults(tmp_path: Path):
    """The regression this merge exists for.

    A project file that only adds a scoring rule used to leave the review with no
    file_roles, no change_patterns and no review_axes — every file classified as
    "other" and the axes down to two emergency values — because the file was validated
    on its own and every field defaults to empty.
    """
    _write_profile(tmp_path, """
candidate_scoring:
  - name: our_own_rule
    patterns:
      - "**/ours/**"
    score_delta: 3
    reason: ours
""")

    profile = ReviewProfileManager(project_root=tmp_path).get_effective_profile()

    assert profile.file_roles == DEFAULT_REVIEW_PROFILE.file_roles
    assert profile.change_patterns == DEFAULT_REVIEW_PROFILE.change_patterns
    assert profile.review_axes.keys() == DEFAULT_REVIEW_PROFILE.review_axes.keys()
    assert "our_own_rule" in {rule.name for rule in profile.candidate_scoring}


def test_resolve_reports_the_source_and_what_the_project_changed(tmp_path: Path):
    _write_profile(tmp_path, """
file_roles:
  tests:
    - "**/my_tests/**"
  generated:
    - "**/gen/**"
remove:
  candidate_scoring:
    - shared_helper
""")

    resolution = ReviewProfileManager(project_root=tmp_path).resolve()

    assert resolution.source == "project"
    assert resolution.report.replaced == ["file_roles.tests"]
    assert resolution.report.added == ["file_roles.generated"]
    assert resolution.report.removed == ["candidate_scoring.shared_helper"]
    assert "shared_helper" not in {r.name for r in resolution.profile.candidate_scoring}


def test_resolve_reports_default_source_when_no_project_file():
    resolution = ReviewProfileManager().resolve()

    assert resolution.source == "default"
    assert resolution.report.is_empty


def test_a_remove_target_that_matches_nothing_is_surfaced_not_raised(tmp_path: Path):
    _write_profile(tmp_path, """
remove:
  file_roles:
    - not_a_real_role
""")

    resolution = ReviewProfileManager(project_root=tmp_path).resolve()

    assert resolution.report.unknown_removals == ["file_roles.not_a_real_role"]
    assert resolution.report.has_warnings
    assert resolution.profile.file_roles == DEFAULT_REVIEW_PROFILE.file_roles


def test_a_misspelled_setting_is_surfaced_rather_than_silently_ignored(tmp_path: Path):
    _write_profile(tmp_path, """
file_rolez:
  tests:
    - "**/x/**"
""")

    resolution = ReviewProfileManager(project_root=tmp_path).resolve()

    assert resolution.report.ignored_keys == ["file_rolez"]
    assert resolution.profile.file_roles == DEFAULT_REVIEW_PROFILE.file_roles


def test_a_profile_that_is_not_a_mapping_raises_clearly(tmp_path: Path):
    _write_profile(tmp_path, "- just\n- a\n- list")

    with pytest.raises(ValueError, match="expected a mapping"):
        ReviewProfileManager(project_root=tmp_path).resolve()
