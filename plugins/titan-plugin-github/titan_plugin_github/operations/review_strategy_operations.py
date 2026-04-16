"""Deterministic operations for selecting PR review focus."""

from ..models.review_enums import (
    ChecklistCategory,
    ExclusionReason,
    FileReadMode,
    FileReviewPriority,
    PRSizeClass,
    ReviewStrategyType,
)
from ..models.review_models import (
    ChangeManifest,
    ExcludedFileEntry,
    FileReviewPlan,
    PRClassification,
    ReviewChecklistItem,
    ReviewPlan,
    ReviewStrategy,
    ScoredReviewCandidate,
)


def classify_pr(manifest: ChangeManifest, comment_entries: int = 0, comment_threads: int = 0) -> PRClassification:
    total_lines = manifest.total_additions + manifest.total_deletions
    files_changed = len(manifest.files)

    if files_changed <= 3 and total_lines <= 80:
        size_class = PRSizeClass.TINY
    elif files_changed <= 8 and total_lines <= 250:
        size_class = PRSizeClass.SMALL
    elif files_changed <= 20 and total_lines <= 700:
        size_class = PRSizeClass.MEDIUM
    elif files_changed <= 40 and total_lines <= 1800:
        size_class = PRSizeClass.LARGE
    else:
        size_class = PRSizeClass.HUGE

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
    )


def score_review_candidates(
    manifest: ChangeManifest,
) -> tuple[list[ScoredReviewCandidate], list[ExcludedFileEntry]]:
    candidates: list[ScoredReviewCandidate] = []
    excluded: list[ExcludedFileEntry] = []

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
        if entry.is_docs:
            excluded.append(ExcludedFileEntry(path=entry.path, reason=ExclusionReason.DOCS))
            continue

        score = 0
        path_lower = entry.path.lower()

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

        domain_tokens = [
            "controller",
            "service",
            "store",
            "client",
            "handler",
            "validator",
            "middleware",
            "repository",
            "viewmodel",
            "presenter",
            "coordinator",
            "manager",
            "api",
            "router",
        ]
        matched_tokens = [token for token in domain_tokens if token in path_lower]
        if matched_tokens:
            score += 4
            reasons.append(f"domain-critical path ({', '.join(matched_tokens[:3])})")

        if any(token in path_lower for token in ("auth", "permission", "security", "payment", "billing")):
            score += 5
            reasons.append("security or access-sensitive area")

        if entry.is_config and entry.total_changes <= 10:
            excluded.append(ExcludedFileEntry(path=entry.path, reason=ExclusionReason.LOW_SIGNAL_CONFIG))
            continue

        if entry.is_test and entry.total_changes <= 20:
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


def select_review_strategy(classification: PRClassification) -> ReviewStrategy:
    if classification.size_class == PRSizeClass.TINY:
        return ReviewStrategy(
            strategy=ReviewStrategyType.DIRECT_FINDINGS,
            size_class=classification.size_class,
            max_focus_files=4,
            max_prompt_chars=14000,
            max_comment_entries=8,
            batching_enabled=False,
            suspicious_empty_findings=False,
        )
    if classification.size_class == PRSizeClass.SMALL:
        return ReviewStrategy(
            strategy=ReviewStrategyType.DIRECT_FINDINGS,
            size_class=classification.size_class,
            max_focus_files=6,
            max_prompt_chars=22000,
            max_comment_entries=10,
            batching_enabled=False,
            suspicious_empty_findings=True,
        )
    if classification.size_class == PRSizeClass.MEDIUM:
        return ReviewStrategy(
            strategy=ReviewStrategyType.LIGHT_PLAN,
            size_class=classification.size_class,
            max_focus_files=8,
            max_prompt_chars=32000,
            max_comment_entries=10,
            batching_enabled=False,
            suspicious_empty_findings=True,
        )
    if classification.size_class == PRSizeClass.LARGE:
        return ReviewStrategy(
            strategy=ReviewStrategyType.BATCHED_FINDINGS,
            size_class=classification.size_class,
            max_focus_files=10,
            max_prompt_chars=24000,
            max_comment_entries=8,
            batching_enabled=True,
            suspicious_empty_findings=True,
        )
    return ReviewStrategy(
        strategy=ReviewStrategyType.BATCHED_FINDINGS,
        size_class=classification.size_class,
        max_focus_files=12,
        max_prompt_chars=18000,
        max_comment_entries=6,
        batching_enabled=True,
        suspicious_empty_findings=True,
    )


def build_deterministic_review_plan(
    candidates: list[ScoredReviewCandidate],
    excluded_files: list[ExcludedFileEntry],
    checklist: list[ReviewChecklistItem],
    strategy: ReviewStrategy,
) -> ReviewPlan:
    focus_candidates = candidates[: strategy.max_focus_files]
    focus_files = [
        FileReviewPlan(
            path=candidate.path,
            priority=candidate.priority,
            read_mode=candidate.suggested_read_mode,
            reasons=candidate.reasons,
        )
        for candidate in focus_candidates
    ]

    review_axes = _select_review_axes(checklist, focus_candidates)
    trimmed_excluded = list(excluded_files)
    for candidate in candidates[strategy.max_focus_files :]:
        trimmed_excluded.append(
            ExcludedFileEntry(
                path=candidate.path,
                reason=ExclusionReason.BUDGET_TRIMMED,
                detail="outside deterministic focus limit",
            )
        )

    return ReviewPlan(
        focus_files=focus_files,
        review_axes=review_axes,
        extra_context_requests=[],
        excluded_files=trimmed_excluded,
    )


def _select_review_axes(
    checklist: list[ReviewChecklistItem],
    focus_candidates: list[ScoredReviewCandidate],
) -> list[ChecklistCategory]:
    if not checklist:
        return [
            ChecklistCategory.FUNCTIONAL_CORRECTNESS,
            ChecklistCategory.ERROR_HANDLING,
        ]

    candidate_paths = [candidate.path.lower() for candidate in focus_candidates]
    selected: list[ChecklistCategory] = []

    for item in checklist:
        if item.id in (ChecklistCategory.FUNCTIONAL_CORRECTNESS, ChecklistCategory.ERROR_HANDLING):
            selected.append(item.id)
            continue
        if item.id == ChecklistCategory.TEST_COVERAGE and any("test" in path or "spec" in path for path in candidate_paths):
            selected.append(item.id)
            continue
        if item.id == ChecklistCategory.API_CONTRACT and any(
            token in path for path in candidate_paths for token in ("api", "schema", "model", "contract")
        ):
            selected.append(item.id)
            continue
        if item.id == ChecklistCategory.DATA_VALIDATION and any(
            token in path for path in candidate_paths for token in ("validator", "request", "form", "serializer")
        ):
            selected.append(item.id)

    if not selected:
        selected = [ChecklistCategory.FUNCTIONAL_CORRECTNESS, ChecklistCategory.ERROR_HANDLING]
    return selected[:5]
