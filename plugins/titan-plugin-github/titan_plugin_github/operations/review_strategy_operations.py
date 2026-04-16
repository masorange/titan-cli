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
    repeated_callsite_files = sum(1 for f in manifest.files if _candidate_group(f.path) == "repeated_callsite")
    high_signal_files = sum(1 for f in manifest.files if _candidate_group(f.path) in {"central_behavior", "entrypoint"})
    repetition_ratio = (repeated_callsite_files / files_changed) if files_changed else 0.0

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

    is_repetitive_migration = files_changed >= 12 and total_lines <= 700 and repetition_ratio >= 0.35
    if size_class == PRSizeClass.HUGE and is_repetitive_migration:
        size_class = PRSizeClass.LARGE

    rationale_parts = [f"{files_changed} files", f"{total_lines} changed lines"]
    if high_signal_files:
        rationale_parts.append(f"{high_signal_files} high-signal files")
    if repeated_callsite_files:
        rationale_parts.append(f"{repeated_callsite_files} repeated call sites")
    if is_repetitive_migration:
        rationale_parts.append("repetitive migration pattern detected")

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
        is_repetitive_migration=is_repetitive_migration,
        rationale=", ".join(rationale_parts),
    )


def score_review_candidates(
    manifest: ChangeManifest,
) -> tuple[list[ScoredReviewCandidate], list[ExcludedFileEntry]]:
    candidates: list[ScoredReviewCandidate] = []
    excluded: list[ExcludedFileEntry] = []
    repeated_callsite_paths = _detect_repeated_callsite_paths(manifest)

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

        if any(token in path_lower for token in ("util", "interceptor", "configuration", "intent")):
            score += 5
            reasons.append("shared helper or policy surface")

        if entry.path in repeated_callsite_paths:
            score -= 2
            reasons.append("repeated call-site migration")

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


def summarize_candidate_clusters(candidates: list[ScoredReviewCandidate]) -> list[dict]:
    """Build a compact summary of repeated candidate groups for planning prompts."""
    clusters: dict[str, list[ScoredReviewCandidate]] = {}
    for candidate in candidates:
        group = _candidate_group(candidate.path)
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
            reason="small enough for direct findings without planning overhead",
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
            reason="limited scope; direct findings remain affordable",
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
            reason="moderate PR size benefits from a lightweight focus plan",
        )
    if classification.size_class == PRSizeClass.LARGE:
        return ReviewStrategy(
            strategy=ReviewStrategyType.BATCHED_FINDINGS,
            size_class=classification.size_class,
            max_focus_files=8 if classification.is_repetitive_migration else 10,
            max_prompt_chars=18000 if classification.is_repetitive_migration else 24000,
            max_comment_entries=8,
            batching_enabled=True,
            suspicious_empty_findings=True,
            reason=(
                "repetitive migration pattern; prioritize shared helpers and representative call sites"
                if classification.is_repetitive_migration
                else "large PR requires batching to keep findings prompts bounded"
            ),
        )
    return ReviewStrategy(
        strategy=ReviewStrategyType.BATCHED_FINDINGS,
        size_class=classification.size_class,
        max_focus_files=12,
        max_prompt_chars=18000,
        max_comment_entries=6,
        batching_enabled=True,
        suspicious_empty_findings=True,
        reason="very large PR requires strict batching and narrow prompt budgets",
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


def _detect_repeated_callsite_paths(manifest: ChangeManifest) -> set[str]:
    repeated: set[str] = set()
    callsite_like = [
        entry for entry in manifest.files
        if _candidate_group(entry.path) == "repeated_callsite" and entry.total_changes <= 20
    ]
    if len(callsite_like) < 4:
        return repeated
    repeated.update(entry.path for entry in callsite_like)
    return repeated


def _candidate_group(path: str) -> str:
    path_lower = path.lower()
    if any(token in path_lower for token in ("/utils/", "/configuration/", "/interceptors/", "intentutils", "customtabsutils")):
        return "central_behavior"
    if any(token in path_lower for token in ("mainactivity", "dispatcher", "listener")):
        return "entrypoint"
    if any(token in path_lower for token in ("screen", "successscreen", "components", "content", "dialog")):
        return "repeated_callsite"
    return "other"
