"""Tests for what one review reads and the budget it runs under."""

from titan_plugin_github.models.review_enums import AttentionTier, ChecklistCategory, FileReadMode
from titan_plugin_github.models.review_models import ReviewChecklistItem
from titan_plugin_github.models.review_profile_models import ReviewAxisRule, ReviewProfile
from titan_plugin_github.operations.attention_operations import AttentionPlan, FileAttention
from titan_plugin_github.operations.review_strategy_operations import (
    build_deterministic_review_plan,
    deep_call_timeout_seconds,
    review_budget,
)


# ============================================================================
# Deep-call timeout derivation
# ============================================================================


def test_deep_call_timeout_matches_the_old_flat_value_for_one_file():
    """A single-file call must not come out with a shorter deadline than the flat 300 s
    it replaces — the base alone reproduces it."""
    budget = review_budget()

    assert deep_call_timeout_seconds(budget, 1) == 300
    # Zero files is not a real batch, but it must not produce a negative allowance.
    assert deep_call_timeout_seconds(budget, 0) == 300


def test_deep_call_timeout_grows_with_the_files_it_was_handed():
    """The measured shape that broke the flat timeout: ten files in one session took
    251 s at medium effort and 363 s at high, against a 300 s deadline."""
    budget = review_budget()

    ten_files = deep_call_timeout_seconds(budget, 10)

    assert ten_files > 363
    assert ten_files == budget.deep_timeout_base_seconds + 9 * budget.deep_timeout_per_file_seconds


def test_deep_call_timeout_is_capped():
    """A hung CLI cannot hold a review open indefinitely, however many files it got."""
    budget = review_budget()

    assert deep_call_timeout_seconds(budget, 500) == budget.deep_timeout_max_seconds


# ============================================================================
# The deterministic plan: the DEEP tier is the selection
# ============================================================================


def _attention(tiers: dict) -> AttentionPlan:
    return AttentionPlan(
        files=[
            FileAttention(path, AttentionTier(tier), "business_logic", f"role:{tier}")
            for path, tier in tiers.items()
        ]
    )


def _item(category: ChecklistCategory) -> ReviewChecklistItem:
    return ReviewChecklistItem(id=category, name=str(category), description="desc")


def test_the_deep_tier_is_the_selection():
    """Every deep file is read, in manifest order, and nothing else is: glance goes to
    the triage and skip is named on screen, so there is no exclusion list to keep."""
    plan = build_deterministic_review_plan(
        _attention({"core.py": "deep", "test_core.py": "glance", "tiny.py": "deep", "README.md": "skip"}),
        [],
        ReviewProfile(),
    )

    assert [f.path for f in plan.focus_files] == ["core.py", "tiny.py"]


def test_every_deep_file_gets_the_same_read_mode():
    """A scorer used to decide this: under 5 points a deep file went in as bare hunks,
    without being marked as openable in the worktree."""
    plan = build_deterministic_review_plan(
        _attention({"a.py": "deep", "b.py": "deep"}), [], ReviewProfile()
    )

    assert {f.read_mode for f in plan.focus_files} == {FileReadMode.EXPANDED_HUNKS}
    assert plan.focus_files[0].reasons == ["role:deep"]


def test_a_large_deep_tier_keeps_every_file():
    """Once a 12-file ceiling sent 12 of 24 deep files to the triage (ragnarok run
    `70777691`). A deep tier is read whole, whatever its size."""
    plan = build_deterministic_review_plan(
        _attention({f"f{i}.py": "deep" for i in range(40)}), [], ReviewProfile()
    )

    assert len(plan.focus_files) == 40


def test_the_axes_come_from_the_deep_files_and_the_profile():
    profile = ReviewProfile(
        review_axes={
            ChecklistCategory.FUNCTIONAL_CORRECTNESS: ReviewAxisRule(always_include=True),
            ChecklistCategory.SECURITY: ReviewAxisRule(patterns=["**/auth/**"]),
            ChecklistCategory.CONCURRENCY: ReviewAxisRule(patterns=["**/*worker*"]),
        }
    )
    checklist = [
        _item(ChecklistCategory.FUNCTIONAL_CORRECTNESS),
        _item(ChecklistCategory.SECURITY),
        _item(ChecklistCategory.CONCURRENCY),
    ]

    plan = build_deterministic_review_plan(
        # The worker is only glanced at, so concurrency is not asked of the deep session.
        _attention({"src/auth/session.py": "deep", "src/jobs/worker.py": "glance"}),
        checklist,
        profile,
    )

    assert plan.review_axes == [ChecklistCategory.FUNCTIONAL_CORRECTNESS, ChecklistCategory.SECURITY]
