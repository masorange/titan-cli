"""Deterministic operations that decide what one review reads, and under what budget."""

from titan_cli.core.logging import get_logger

from ..models.review_enums import AttentionTier
from ..models.review_models import (
    FileReviewPlan,
    ReviewBudget,
    ReviewChecklistItem,
    ReviewPlan,
)
from ..models.review_profile_models import ReviewProfile
from .review_profile_operations import select_review_axes

logger = get_logger(__name__)


# How long one deep call may run. Derived from the files it was handed rather than flat,
# because the duration of an agentic session tracks how much code it has to open: ten
# files in one session measured 251 s at medium effort and 363 s at high, while the flat
# 300 s these replace was chosen when a batch held a single file. The base alone
# reproduces that old 300 s for a one-file call, so nothing gets a shorter deadline than
# it had; the per-file allowance is what the packed shapes need.
#
# The margin over the measurement is intentional. A timeout does not bound the bill --
# effort and model choice do -- so the only thing a tight deadline buys is a review that
# dies at 99%. The cap exists so a genuinely hung CLI cannot hold a review open
# indefinitely, and Ctrl+C reaches the call before then.
DEEP_TIMEOUT_BASE_SECONDS = 300
DEEP_TIMEOUT_PER_FILE_SECONDS = 120
DEEP_TIMEOUT_MAX_SECONDS = 1500


def review_budget() -> ReviewBudget:
    """The budget every review runs under.

    A function rather than a module constant so callers cannot mutate a shared object,
    and so a future per-project override has one place to land.
    """
    return ReviewBudget(
        deep_timeout_base_seconds=DEEP_TIMEOUT_BASE_SECONDS,
        deep_timeout_per_file_seconds=DEEP_TIMEOUT_PER_FILE_SECONDS,
        deep_timeout_max_seconds=DEEP_TIMEOUT_MAX_SECONDS,
    )


def deep_call_timeout_seconds(budget: ReviewBudget, file_count: int) -> int:
    """Seconds one deep findings call may run, given how many files it was handed.

    A file count of zero or one yields the base alone, so a single-file call keeps the
    deadline it has always had. The result is capped, and the caller logs it: the
    constants behind it were set from one measured run and are meant to be corrected
    from the logged values rather than re-guessed.
    """
    extra_files = max(0, file_count - 1)
    derived = budget.deep_timeout_base_seconds + extra_files * budget.deep_timeout_per_file_seconds
    return min(derived, budget.deep_timeout_max_seconds)


def build_deterministic_review_plan(
    attention_plan,
    checklist: list[ReviewChecklistItem],
    review_profile: ReviewProfile,
) -> ReviewPlan:
    """Decide what the deep session reads, without asking a model or scoring anything.

    The deep tier IS the selection: every deep file is reviewed in depth, in manifest
    order. The glance files join the same session (see `build_review_context_package`),
    so nothing reviewable is left out and there is no exclusion list to keep.

    Two layers that sat in front of this are gone. An AI planning call (run 4fd7f345: 92,463
    input tokens to choose 7 of the 9 files the tiers had already marked deep), and a
    scorer that ranked files for a 12-file cut which no longer exists -- and which, while
    it lived, also decided how much context each deep file got: under 5 points a deep file
    went in as bare hunks without being marked as openable.
    """
    deep_entries = [entry for entry in attention_plan.files if entry.tier == AttentionTier.DEEP]
    focus_files = [
        FileReviewPlan(
            path=entry.path,
            reasons=[entry.reason],
        )
        for entry in deep_entries
    ]
    return ReviewPlan(
        focus_files=focus_files,
        review_axes=select_review_axes(checklist, [entry.path for entry in deep_entries], review_profile),
    )
