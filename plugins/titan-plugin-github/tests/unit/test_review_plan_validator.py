from titan_plugin_github.models.review_models import ChangeManifest, PullRequestManifest
from titan_plugin_github.models.validators import ReviewPlanValidator


def _make_manifest() -> ChangeManifest:
    return ChangeManifest(
        pr=PullRequestManifest(
            number=1,
            title="Test PR",
            base="main",
            head="feat/test",
            author="alex",
            description="Body",
        ),
        files=[],
        total_additions=0,
        total_deletions=0,
    )


def test_validator_uses_all_checklist_ids_when_none_is_passed():
    validator = ReviewPlanValidator(_make_manifest(), offered_checklist_ids=None)

    assert "functional_correctness" in validator.offered_checklist_ids
    assert "error_handling" in validator.offered_checklist_ids


def test_validator_preserves_explicit_empty_checklist_ids():
    validator = ReviewPlanValidator(_make_manifest(), offered_checklist_ids=frozenset())

    assert validator.offered_checklist_ids == frozenset()
