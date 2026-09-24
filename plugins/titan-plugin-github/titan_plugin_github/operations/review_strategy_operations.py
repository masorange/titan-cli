"""Deterministic operations that decide what one review reads, and under what budget."""

from titan_cli.core.logging import get_logger

from ..models.review_enums import AttentionTier, FileReadMode
from ..models.review_models import (
    FileReviewPlan,
    ReviewBudget,
    ReviewChecklistItem,
    ReviewPlan,
)
from ..models.review_profile_models import ReviewProfile
from .review_profile_operations import select_review_axes

logger = get_logger(__name__)


# One budget for every review, in Titan, generic. Not derived from a size label: the
# five-tier table it replaces gave a 108-file PR and a 500-file PR the same 12 files
# because HUGE was its last rung.
#
# What the deep batch may be HANDED. It does not bound what the model then reads from the
# worktree, which is the real cost - it only stops one prompt from being absurd.
#
# It was 18,000, a figure sized when a batch held ONE file. The deep batch now holds every
# deep file, and at 18,000 the budget went back to deciding the work: each file's share of
# it came to ~1,600 chars on PR 251, under which almost every file loses its inline diff
# and with it the snippet an inline comment anchors to (24 of 29 anchors in run 6c438999
# resolved via a unique snippet).
#
# Raising it is cheap in the unit that actually pays. The findings calls in run 6c438999
# reported ~3,300 INPUT tokens each against 100,365 output tokens for $7.4581 -- ~95% of
# the bill is output. 120,000 chars is ~30,000 input tokens, about $0.45 once at opus
# rates, and input is the half that caches. Characters were never the deep tier's cost
# unit (D-002); this ceiling exists so a pathological PR cannot build a megabyte prompt,
# and `fit_batch_to_budget` still enforces it against the real string.
DEEP_MAX_PROMPT_CHARS = 120000

# The triage cannot read the repo, so here the prompt IS the spend and characters are
# the honest unit. Sized so an ordinary PR is ONE call: at 18,000 chars ragnarok PR 3692's
# 24 glance files (144,805 chars of diff) took 12 calls, each paying the CLI's own fixed
# context (~$0.08 on claude) -- $1.18 for the triage against $0.66 for the deep review --
# and no call could rank its questions against the other eleven's. 200,000 chars is ~50k
# tokens, inside every supported CLI's context window.
TRIAGE_MAX_PROMPT_CHARS = 200000

MAX_COMMENT_ENTRIES = 10

# How long one deep call may run. Derived from the files it was handed rather than flat,
# because the duration of an agentic session tracks how much code it has to open: ten
# files in one session measured 251 s at medium effort and 363 s at high, while the flat
# 300 s these replace was chosen when a batch held a single file. The base alone
# reproduces that old 300 s for a one-file call, so nothing gets a shorter deadline than
# it had; the per-file allowance is what the packed shapes need.
#
# The margin over the measurement is intentional. A timeout does not bound the bill --
# effort and model choice do -- so the only thing a tight deadline buys is a review that
# dies at 99% and, before the split path below existed, died silently. The cap exists so
# a genuinely hung CLI cannot hold a review open indefinitely, and Ctrl+C reaches the
# call before then.
DEEP_TIMEOUT_BASE_SECONDS = 300
DEEP_TIMEOUT_PER_FILE_SECONDS = 120
DEEP_TIMEOUT_MAX_SECONDS = 1500


def review_budget() -> ReviewBudget:
    """The budget every review runs under.

    A function rather than a module constant so callers cannot mutate a shared object,
    and so a future per-project override has one place to land.
    """
    return ReviewBudget(
        deep_max_prompt_chars=DEEP_MAX_PROMPT_CHARS,
        triage_max_prompt_chars=TRIAGE_MAX_PROMPT_CHARS,
        max_comment_entries=MAX_COMMENT_ENTRIES,
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

    The deep tier IS the selection: every deep file is read, in manifest order, with its
    diff inline and the file open in the worktree. Everything else that is not skipped
    goes to the triage, so nothing reviewable is left out and there is no exclusion list
    to keep.

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
            read_mode=FileReadMode.EXPANDED_HUNKS,
            reasons=[entry.reason],
        )
        for entry in deep_entries
    ]
    return ReviewPlan(
        focus_files=focus_files,
        review_axes=select_review_axes(checklist, [entry.path for entry in deep_entries], review_profile),
    )
