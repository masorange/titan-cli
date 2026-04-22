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
