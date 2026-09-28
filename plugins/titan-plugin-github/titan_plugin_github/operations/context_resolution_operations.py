"""Operations for building the deep review session from a review plan."""

from pathlib import Path
from typing import Optional

from titan_cli.core.logging import get_logger

from .prompt_formatting_operations import review_pr_description
from ..models.review_enums import AttentionTier
from ..models.review_models import (
    ChangeManifest,
    FileContextEntry,
    FocusContextBatch,
    ReviewChecklistItem,
    ReviewContextPackage,
    ReviewPlan,
)

logger = get_logger(__name__)


def read_file_content(path: str, cwd: Optional[str] = None) -> Optional[str]:
    try:
        base = Path(cwd) if cwd else Path.cwd()
        file_path = base / path
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError) as e:
        logger.debug("file_read_failed", path=path, error=str(e))
    return None


DEEP_BATCH_ID = "deep_1"
"""The one deep session of a review.

Singular by design (D-014): the session is the unit of understanding, and what it
understands about one file is what lets it see the defect that spans two.
"""


def build_review_context_package(
    plan: ReviewPlan,
    manifest: ChangeManifest,
    checklist: list[ReviewChecklistItem],
    review_material: dict[str, bool],
    cwd: Optional[str] = None,
    attention_plan=None,
    review_profile=None,
) -> ReviewContextPackage:
    """
    Build the one deep session over every reviewable file.

    ``review_material`` maps every changed path to whether its base version was written:
    the diffs and base versions are files in the review worktree, so the prompt carries a
    pointer per file and no diff.

    ``attention_plan``, when given, puts the shape of the WHOLE change on the batch --
    one content-free line per changed file with its role and tier -- and adds the glance
    files to the session's own. Without it the session only reviews the deep files.
    """
    applicable_ids = set(plan.review_axes)
    # Falling back to EVERY offered axis, not two of them: reaching here means the plan
    # selected no axis at all, which is an upstream failure, and the safe direction is to
    # ask about everything the project declared rather than about almost nothing.
    checklist_applicable = [item for item in checklist if item.id in applicable_ids] or list(checklist)

    # More than the one-line cap a per-file batch got: this batch judges the change
    # against what the PR says it does, so it needs the claim in full. Still capped --
    # a PR description can be a novel, and the review is not a reading exercise.
    pr_intent = review_pr_description(manifest.pr.description) if manifest.pr else None

    # The deep session reads the DEEP and GLANCE files; SKIP files (lockfiles, renames,
    # generated output) are declared, on screen and in the log, and left out. On PR 251
    # a file the plan had tiered skip still went into the review when `focus_files` came
    # straight from a scorer, which made the tiers decoration.
    paths = [file_plan.path for file_plan in plan.focus_files]
    if attention_plan is not None:
        deep_paths = set(attention_plan.paths_for(AttentionTier.DEEP))
        excluded = [path for path in paths if path not in deep_paths]
        if excluded:
            logger.info(
                "focus_files_outside_deep_tier",
                dropped=len(excluded),
                kept=len(paths) - len(excluded),
                paths=sorted(excluded),
            )
        paths = [path for path in paths if path in deep_paths]
        known = set(paths)
        paths += [path for path in attention_plan.paths_for(AttentionTier.GLANCE) if path not in known]

    context_docs = resolve_context_docs(
        review_profile.context_docs if review_profile else [],
        cwd,
        review_profile.max_context_docs if review_profile else 0,
    )

    change_shape: list[str] = []
    if attention_plan is not None:
        from .attention_operations import build_change_shape_lines

        change_shape = build_change_shape_lines(attention_plan, manifest.files, set(paths))

    from .attention_operations import order_by_relation
    from .manifest_operations import is_test_file
    from .review_material_operations import review_material_hint

    # Read in groups: a file next to the ones it belongs with, each test right after its
    # subject, so the question that spans them comes up while both are in view.
    ordered = order_by_relation(paths, lambda path: is_test_file(path, review_profile))
    files_context = {
        path: FileContextEntry(path=path, review_hint=review_material_hint(path, review_material.get(path, False)))
        for path in ordered
    }
    batch = FocusContextBatch(
        batch_id=DEEP_BATCH_ID,
        files_context=files_context,
        checklist_applicable=checklist_applicable,
        pr_manifest=manifest.pr,
        change_shape=change_shape,
        context_docs=context_docs,
        pr_intent=pr_intent,
    )
    from .findings_operations import build_findings_prompt_parts

    logger.info(
        "deep_session_built",
        files=len(files_context),
        with_base_version=sum(1 for path in ordered if review_material.get(path)),
        prompt_actual_chars=len(build_findings_prompt_parts(batch)["prompt"]),
    )
    return ReviewContextPackage(batches=[batch])


def resolve_context_docs(
    patterns: list[str],
    cwd: Optional[str],
    limit: int,
) -> list[str]:
    """Project documents the session should read before judging the code.

    Returns PATHS, never content: the session opens them from the working tree itself,
    so a whole architecture document costs a line of prompt instead of thousands of
    characters charged to every call.

    Only paths that exist under ``cwd`` are returned, so a stale or aspirational entry
    is silently harmless and the defaults can name conventional files (`CLAUDE.md`,
    `AGENTS.md`, a harness README) without assuming any repo has them. Patterns keep
    their declared order — a project puts its load-bearing document first — and the
    result is capped at ``limit``, because every document is reading time inside the one
    deep call.
    """
    if not cwd or limit <= 0 or not patterns:
        return []

    # Resolved, because the containment check below is only meaningful against a real
    # path: `repo/../outside.md` is lexically "inside" repo and is not.
    root = Path(cwd).resolve()
    resolved: list[str] = []
    for pattern in patterns:
        if len(resolved) >= limit:
            break
        # A literal path is checked directly; anything with a wildcard is expanded and
        # sorted so two runs of the same review offer the same reading in the same order.
        matches = sorted(root.glob(pattern)) if any(ch in pattern for ch in "*?[") else [root / pattern]
        for match in matches:
            if len(resolved) >= limit:
                break
            if not match.is_file():
                continue
            try:
                relative = match.resolve().relative_to(root).as_posix()
            except ValueError:
                # A pattern that escapes the working tree (`../secrets.md`) is not this
                # project's documentation, whoever wrote it.
                continue
            if relative not in resolved:
                resolved.append(relative)

    dropped = len(patterns) - len(resolved)
    logger.info(
        "review_context_docs_resolved",
        declared=len(patterns),
        offered=len(resolved),
        limit=limit,
        paths=resolved,
        patterns_without_a_file=max(0, dropped),
    )
    return resolved
