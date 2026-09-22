from pathlib import Path

import pytest

from titan_plugin_github.checklists.defaults import DEFAULT_REVIEW_CHECKLIST
from titan_plugin_github.managers.checklist_manager import ChecklistManager


def test_returns_default_checklist_contents():
    checklist = ChecklistManager().get_effective_checklist()

    assert checklist == DEFAULT_REVIEW_CHECKLIST


def test_returns_defensive_copy():
    checklist = ChecklistManager().get_effective_checklist()
    checklist[0].name = "Changed"

    fresh = ChecklistManager().get_effective_checklist()

    assert fresh[0].name == DEFAULT_REVIEW_CHECKLIST[0].name


def test_loads_project_checklist_from_yaml(tmp_path: Path):
    review_dir = tmp_path / ".titan" / "review"
    review_dir.mkdir(parents=True)
    (review_dir / "checklist.yaml").write_text(
        """
version: 1
items:
  - id: functional_correctness
    name: Functional Correctness
    description: Check behavior
    relevant_file_patterns: []
  - id: security
    name: Security
    description: Check auth and secrets
    relevant_file_patterns:
      - "**/auth/**"
""".strip(),
        encoding="utf-8",
    )

    checklist = ChecklistManager(project_root=tmp_path).get_effective_checklist()

    by_id = {item.id: item for item in checklist}
    # The project's items merge onto Titan's twelve: the known id is replaced in place
    # and `security` (already a default category) gets the project's patterns. Adding
    # one item must not cost the other eleven.
    assert by_id["functional_correctness"].description == "Check behavior"
    assert by_id["security"].relevant_file_patterns == ["**/auth/**"]
    assert len(checklist) == len(DEFAULT_REVIEW_CHECKLIST)
    assert checklist[0].id == DEFAULT_REVIEW_CHECKLIST[0].id


def test_invalid_checklist_yaml_raises_clear_error(tmp_path: Path):
    review_dir = tmp_path / ".titan" / "review"
    review_dir.mkdir(parents=True)
    (review_dir / "checklist.yaml").write_text("items: [", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid review checklist YAML"):
        ChecklistManager(project_root=tmp_path).get_effective_checklist()


def test_invalid_checklist_category_raises_clear_error(tmp_path: Path):
    review_dir = tmp_path / ".titan" / "review"
    review_dir.mkdir(parents=True)
    (review_dir / "checklist.yaml").write_text(
        """
version: 1
items:
  - id: made_up_category
    name: Nope
    description: Invalid
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid review checklist configuration"):
        ChecklistManager(project_root=tmp_path).get_effective_checklist()


def _write_checklist(tmp_path: Path, body: str) -> None:
    review_dir = tmp_path / ".titan" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "checklist.yaml").write_text(body.strip(), encoding="utf-8")


def test_tuning_one_item_keeps_the_other_eleven(tmp_path: Path):
    """A project checklist used to REPLACE the defaults, so writing one item cost the
    other eleven — and nothing on screen told the difference between "we wrote one
    item" and "we review one thing".

    Note a project cannot ADD a category: `ChecklistCategory` has exactly 12 members
    and all 12 are already defaults, so the only project moves are retune and remove.
    """
    _write_checklist(tmp_path, """
version: 1
items:
  - id: performance
    name: Our Performance Bar
    description: ours
    relevant_file_patterns:
      - "**/*query*"
""")

    checklist = ChecklistManager(project_root=tmp_path).get_effective_checklist()

    assert len(checklist) == len(DEFAULT_REVIEW_CHECKLIST)
    assert checklist[0].id == DEFAULT_REVIEW_CHECKLIST[0].id
    by_id = {str(item.id): item for item in checklist}
    assert by_id["performance"].name == "Our Performance Bar"
    assert by_id["performance"].relevant_file_patterns == ["**/*query*"]


def test_resolve_reports_what_the_project_changed(tmp_path: Path):
    _write_checklist(tmp_path, """
version: 1
items:
  - id: error_handling
    name: Errors
    description: ours
    relevant_file_patterns: []
remove:
  - test_coverage
""")

    resolution = ChecklistManager(project_root=tmp_path).resolve()

    assert resolution.source == "project"
    assert resolution.report.replaced == ["error_handling"]
    assert resolution.report.removed == ["test_coverage"]
    assert "test_coverage" not in {str(item.id) for item in resolution.checklist}


def test_a_repeated_removal_is_not_reported_as_a_mismatch(tmp_path: Path):
    """Removing the same id twice is a duplicate line in a config file, not a user
    error — warning about the second pass would be a warning about our own loop."""
    _write_checklist(tmp_path, """
version: 1
items: []
remove:
  - security
  - security
""")

    resolution = ChecklistManager(project_root=tmp_path).resolve()

    assert resolution.report.removed == ["security"]
    assert resolution.report.unknown_removals == []


def test_removing_an_absent_checklist_id_is_surfaced_not_raised(tmp_path: Path):
    _write_checklist(tmp_path, """
version: 1
items: []
remove:
  - security
""")

    resolution = ChecklistManager(project_root=tmp_path).resolve()

    assert resolution.report.removed == ["security"]

    second = ChecklistManager(project_root=tmp_path)
    resolution = second.resolve()
    assert "security" not in {str(i.id) for i in resolution.checklist}


def test_a_checklist_whose_items_are_not_a_list_raises_clearly(tmp_path: Path):
    _write_checklist(tmp_path, "items: not-a-list")

    with pytest.raises(ValueError, match="'items' must be a list"):
        ChecklistManager(project_root=tmp_path).resolve()
