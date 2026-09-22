"""Deterministic operations for selecting PR review focus."""

from .review_profile_operations import (
    classify_file_role,
    is_reviewable_documentation,
    match_change_patterns,
    matching_scoring_rules,
    select_review_axes,
)
from titan_cli.core.logging import get_logger

from ..models.review_enums import (
    AttentionTier,
    ExclusionReason,
    FileReadMode,
    FileReviewPriority,
    PRSizeClass,
)
from ..models.review_profile_models import ReviewProfile
from ..models.review_models import (
    ChangeManifest,
    ExcludedFileEntry,
    FileReviewPlan,
    PRClassification,
    ReviewBudget,
    ReviewChecklistItem,
    ReviewPlan,
    ScoredReviewCandidate,
)
from ..review_profiles import DEFAULT_REVIEW_PROFILE

logger = get_logger(__name__)


def classify_pr(
    manifest: ChangeManifest,
    comment_entries: int = 0,
    comment_threads: int = 0,
    review_profile: ReviewProfile | None = None,
) -> PRClassification:
    review_profile = review_profile or DEFAULT_REVIEW_PROFILE
    total_lines = manifest.total_additions + manifest.total_deletions
    files_changed = len(manifest.files)
    repeated_callsite_files = sum(
        1 for f in manifest.files if "repeated_callsite" in match_change_patterns(f.path, review_profile)
    )
    high_signal_files = sum(
        1
        for f in manifest.files
        if {"central_behavior", "entrypoint"}.intersection(match_change_patterns(f.path, review_profile))
    )
    repetition_ratio = (repeated_callsite_files / files_changed) if files_changed else 0.0
    roles = sorted(
        {
            classify_file_role(
                f.path,
                review_profile,
                is_test=f.is_test,
                is_docs=f.is_docs,
                is_generated=f.is_generated,
                is_config=f.is_config,
            )
            for f in manifest.files
        }
    )
    role_count = len(roles)
    active_review = comment_threads >= 5 or comment_entries >= 10
    is_repetitive_migration = files_changed >= 12 and total_lines <= 700 and repetition_ratio >= 0.35
    complexity_score = _compute_complexity_score(
        files_changed=files_changed,
        total_lines=total_lines,
        high_signal_files=high_signal_files,
        role_count=role_count,
        is_repetitive_migration=is_repetitive_migration,
        repetition_ratio=repetition_ratio,
    )
    size_class = _score_to_size_class(complexity_score)

    if files_changed >= 35 and total_lines >= 4000 and role_count >= 3:
        size_class = PRSizeClass.HUGE

    if size_class == PRSizeClass.HUGE and is_repetitive_migration:
        size_class = PRSizeClass.LARGE
    elif size_class == PRSizeClass.HUGE and files_changed <= 15 and role_count <= 4 and high_signal_files <= 6:
        size_class = PRSizeClass.LARGE
    elif size_class == PRSizeClass.LARGE and files_changed <= 8 and total_lines <= 300:
        size_class = PRSizeClass.SMALL

    rationale_parts = [f"{files_changed} files", f"{total_lines} changed lines"]
    if high_signal_files:
        rationale_parts.append(f"{high_signal_files} high-signal files")
    if repeated_callsite_files:
        rationale_parts.append(f"{repeated_callsite_files} repeated call sites")
    if role_count:
        rationale_parts.append(f"roles: {', '.join(roles)}")
    if active_review:
        rationale_parts.append("active review in progress")
    if is_repetitive_migration:
        rationale_parts.append("repetitive migration pattern detected")
    rationale_parts.append(f"complexity score {complexity_score}")

    return PRClassification(
        size_class=size_class,
        files_changed=files_changed,
        total_lines_changed=total_lines,
        doc_files=sum(1 for f in manifest.files if f.is_docs),
        test_files=sum(1 for f in manifest.files if f.is_test),
        config_files=sum(1 for f in manifest.files if f.is_config),
        generated_files=sum(1 for f in manifest.files if f.is_generated),
        comment_threads=comment_threads,
        comment_entries=comment_entries,
        high_signal_files=high_signal_files,
        repeated_callsite_files=repeated_callsite_files,
        role_count=role_count,
        roles=roles,
        complexity_score=complexity_score,
        active_review=active_review,
        is_repetitive_migration=is_repetitive_migration,
        rationale=", ".join(rationale_parts),
    )


def _compute_complexity_score(
    *,
    files_changed: int,
    total_lines: int,
    high_signal_files: int,
    role_count: int,
    is_repetitive_migration: bool,
    repetition_ratio: float,
) -> int:
    # The size class measures the CODE, so review activity deliberately plays no part
    # here: comments don't make a PR bigger, and counting them meant a review's own
    # published comments could push the same unchanged PR into a bigger size class on
    # the next run. Review activity is captured separately as `active_review`.
    score = 0

    if files_changed <= 3:
        score += 0
    elif files_changed <= 8:
        score += 2
    elif files_changed <= 15:
        score += 3
    elif files_changed <= 40:
        score += 4
    else:
        score += 6

    if total_lines <= 80:
        score += 0
    elif total_lines <= 300:
        score += 1
    elif total_lines <= 900:
        score += 2
    elif total_lines <= 2500:
        score += 3
    elif total_lines <= 10000:
        score += 4
    else:
        score += 6

    if high_signal_files >= 8:
        score += 3
    elif high_signal_files >= 4:
        score += 2
    elif high_signal_files >= 1:
        score += 1

    if role_count >= 6:
        score += 3
    elif role_count >= 4:
        score += 2
    elif role_count >= 2:
        score += 1

    if is_repetitive_migration:
        score -= 2
    elif repetition_ratio >= 0.35:
        score -= 1

    return max(0, score)


def _score_to_size_class(score: int) -> PRSizeClass:
    if score <= 2:
        return PRSizeClass.TINY
    if score <= 4:
        return PRSizeClass.SMALL
    if score <= 6:
        return PRSizeClass.MEDIUM
    if score <= 10:
        return PRSizeClass.LARGE
    return PRSizeClass.HUGE


def score_review_candidates(
    manifest: ChangeManifest,
    review_profile: ReviewProfile | None = None,
) -> tuple[list[ScoredReviewCandidate], list[ExcludedFileEntry]]:
    review_profile = review_profile or DEFAULT_REVIEW_PROFILE
    candidates: list[ScoredReviewCandidate] = []
    excluded: list[ExcludedFileEntry] = []
    repeated_callsite_paths = _detect_repeated_callsite_paths(manifest, review_profile)

    for entry in manifest.files:
        reasons: list[str] = []

        if entry.status.value == "deleted":
            excluded.append(ExcludedFileEntry(path=entry.path, reason=ExclusionReason.DELETED))
            continue
        if entry.is_rename_only:
            excluded.append(ExcludedFileEntry(path=entry.path, reason=ExclusionReason.RENAME_ONLY))
            continue
        if entry.is_lockfile:
            excluded.append(ExcludedFileEntry(path=entry.path, reason=ExclusionReason.LOCKFILE))
            continue
        if entry.is_generated:
            excluded.append(ExcludedFileEntry(path=entry.path, reason=ExclusionReason.GENERATED))
            continue
        if entry.is_docs and not is_reviewable_documentation(entry.path, review_profile):
            excluded.append(ExcludedFileEntry(path=entry.path, reason=ExclusionReason.DOCS))
            continue

        score = 0
        if entry.total_changes >= 200:
            score += 6
            reasons.append("large change set")
        elif entry.total_changes >= 80:
            score += 4
            reasons.append("medium change set")
        elif entry.total_changes >= 20:
            score += 2
            reasons.append("non-trivial change")

        if entry.status.value == "added":
            score += 3
            reasons.append("new file")

        if not entry.is_test:
            # Scoring rules describe production roles (viewmodels, utils, config
            # surfaces...). A test file matching them by name would inherit the
            # criticality of the code it tests; tests score on their own change
            # size plus the explicit test bonus below.
            for rule in matching_scoring_rules(entry.path, review_profile):
                score += rule.score_delta
                reasons.append(rule.reason)

        if entry.path in repeated_callsite_paths:
            score -= 2
            reasons.append("repeated call-site migration")

        if (
            entry.is_config
            and entry.total_changes <= review_profile.candidate_exclusions.low_signal_config_max_changes
        ):
            excluded.append(ExcludedFileEntry(path=entry.path, reason=ExclusionReason.LOW_SIGNAL_CONFIG))
            continue

        if entry.is_test and entry.total_changes <= review_profile.candidate_exclusions.low_signal_test_max_changes:
            excluded.append(ExcludedFileEntry(path=entry.path, reason=ExclusionReason.LOW_SIGNAL_TEST))
            continue
        if entry.is_test:
            score += 1
            reasons.append("test file with meaningful changes")

        if score <= 0:
            score = 1
            reasons.append("changed source file")

        if score >= 10:
            priority = FileReviewPriority.HIGH
            read_mode = FileReadMode.EXPANDED_HUNKS
        elif score >= 5:
            priority = FileReviewPriority.MEDIUM
            read_mode = FileReadMode.EXPANDED_HUNKS
        else:
            priority = FileReviewPriority.LOW
            read_mode = FileReadMode.HUNKS_ONLY

        candidates.append(
            ScoredReviewCandidate(
                path=entry.path,
                score=score,
                priority=priority,
                suggested_read_mode=read_mode,
                reasons=reasons,
            )
        )

    candidates.sort(key=lambda item: (item.score, item.priority == FileReviewPriority.HIGH), reverse=True)
    return candidates, excluded


def summarize_candidate_clusters(
    candidates: list[ScoredReviewCandidate],
    review_profile: ReviewProfile | None = None,
) -> list[dict]:
    """Build a compact summary of repeated candidate groups for planning prompts."""
    review_profile = review_profile or DEFAULT_REVIEW_PROFILE
    clusters: dict[str, list[ScoredReviewCandidate]] = {}
    for candidate in candidates:
        group = _candidate_group(candidate.path, review_profile)
        clusters.setdefault(group, []).append(candidate)

    summary: list[dict] = []
    for group, grouped_candidates in clusters.items():
        if len(grouped_candidates) < 3:
            continue
        summary.append(
            {
                "group": group,
                "count": len(grouped_candidates),
                "representatives": [candidate.path for candidate in grouped_candidates[:3]],
            }
        )
    summary.sort(key=lambda item: item["count"], reverse=True)
    return summary[:5]


# One budget for every review, in Titan, generic. Not derived from a size label: the
# five-tier table it replaces gave a 108-file PR and a 500-file PR the same 12 files
# because HUGE was its last rung.
#
# `MAX_DEEP_SESSIONS` is the number that actually pays the bill - each deep read is a
# full CLI session, and what it generates is the spend: measured 2026-09-22 on PR 251,
# nine sessions produced 82k output tokens for $6.46 where one session over the same ten
# files produced 26k for $2.52. Sessions are the unit because each one reasons from
# scratch and, running independently, cannot share the prompt cache the single session
# read 2M tokens from. (An earlier note here claimed a ~$0.26 per-session floor measured
# by probing with a one-word prompt; that figure was almost entirely cache creation from
# this repo's own CLAUDE.md and does not apply to review calls, which report no cache.)
# Twelve keeps the spend at the level the old HUGE tier already cost.
MAX_DEEP_SESSIONS = 12

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

# The glance tier cannot read the repo, so here the prompt IS the spend and characters
# are the honest unit. The per-batch file cap is separate because a prompt that fits the
# char budget can still hold too many files to judge carefully.
SCAN_MAX_PROMPT_CHARS = 18000
SCAN_MAX_FILES_PER_BATCH = 12

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
        max_deep_sessions=MAX_DEEP_SESSIONS,
        deep_max_prompt_chars=DEEP_MAX_PROMPT_CHARS,
        scan_max_prompt_chars=SCAN_MAX_PROMPT_CHARS,
        scan_max_files_per_batch=SCAN_MAX_FILES_PER_BATCH,
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
    candidates: list[ScoredReviewCandidate],
    excluded_files: list[ExcludedFileEntry],
    checklist: list[ReviewChecklistItem],
    budget: ReviewBudget,
    review_profile: ReviewProfile | None = None,
    attention_plan=None,
) -> ReviewPlan:
    """Decide what the deep session reads, without asking a model.

    With an ``attention_plan``, the DEEP tier IS the selection: every deep file is read,
    in score order, and nothing else is. `max_deep_sessions` stops being a selection rule
    and becomes the overflow guard it was always described as.

    This replaced an AI planning call, and the measurement is why. On run 4fd7f345 that
    call spent 92,463 input tokens and 38.8 s choosing files -- and chose 7 of the 9 the
    attention plan had already marked deep, spending two of its slots on test files the
    plan had tiered `glance`. `titan_cli/core/oauth/__init__.py` and `exceptions.py` went
    unreviewed as a result. A call that subtracts coverage a deterministic rule already
    decided is not worth its tokens.

    Without an attention plan (a step run standalone), the old score-order cut applies.
    """
    review_profile = review_profile or DEFAULT_REVIEW_PROFILE

    if attention_plan is not None:
        deep_paths = set(attention_plan.paths_for(AttentionTier.DEEP))
        selected = [candidate for candidate in candidates if candidate.path in deep_paths]
        not_selected = [
            (candidate, _exclusion_for_tier(attention_plan, candidate.path))
            for candidate in candidates
            if candidate.path not in deep_paths
        ]
    else:
        selected = candidates[: budget.max_deep_sessions]
        not_selected = [
            (candidate, "outside deterministic focus limit")
            for candidate in candidates[budget.max_deep_sessions :]
        ]

    overflow: list[ScoredReviewCandidate] = []
    if len(selected) > budget.max_deep_sessions:
        overflow = selected[budget.max_deep_sessions :]
        selected = selected[: budget.max_deep_sessions]
        logger.warning(
            "deep_tier_exceeds_session_budget",
            deep_files=len(selected) + len(overflow),
            max_deep_sessions=budget.max_deep_sessions,
            not_read=sorted(candidate.path for candidate in overflow),
        )

    focus_files = [
        FileReviewPlan(
            path=candidate.path,
            priority=candidate.priority,
            read_mode=candidate.suggested_read_mode,
            reasons=candidate.reasons,
        )
        for candidate in selected
    ]

    review_axes = select_review_axes(checklist, selected, review_profile)
    trimmed_excluded = list(excluded_files)
    for candidate, detail in not_selected:
        trimmed_excluded.append(
            ExcludedFileEntry(
                path=candidate.path,
                reason=ExclusionReason.BUDGET_TRIMMED,
                detail=detail,
            )
        )
    for candidate in overflow:
        trimmed_excluded.append(
            ExcludedFileEntry(
                path=candidate.path,
                reason=ExclusionReason.BUDGET_TRIMMED,
                detail=f"deep, but beyond the {budget.max_deep_sessions}-file session limit",
            )
        )

    return ReviewPlan(
        focus_files=focus_files,
        review_axes=review_axes,
        extra_context_requests=[],
        excluded_files=trimmed_excluded,
    )


def _exclusion_for_tier(attention_plan, path: str) -> str:
    """Why a candidate is not in the deep session, named by its tier."""
    for entry in attention_plan.files:
        if entry.path == path:
            return f"tiered {entry.tier.value} ({entry.reason})"
    return "not in the attention plan"


def _detect_repeated_callsite_paths(
    manifest: ChangeManifest,
    review_profile: ReviewProfile,
) -> set[str]:
    repeated: set[str] = set()
    callsite_like = [
        entry for entry in manifest.files
        if "repeated_callsite" in match_change_patterns(entry.path, review_profile) and entry.total_changes <= 20
    ]
    if len(callsite_like) < 4:
        return repeated
    repeated.update(entry.path for entry in callsite_like)
    return repeated


def _candidate_group(path: str, review_profile: ReviewProfile) -> str:
    matches = match_change_patterns(path, review_profile)
    if "central_behavior" in matches:
        return "central_behavior"
    if "entrypoint" in matches:
        return "entrypoint"
    if "repeated_callsite" in matches:
        return "repeated_callsite"
    return "other"
