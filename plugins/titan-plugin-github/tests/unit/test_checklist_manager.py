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

    assert [item.id for item in checklist] == ["functional_correctness", "security"]
    assert checklist[1].relevant_file_patterns == ["**/auth/**"]


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
