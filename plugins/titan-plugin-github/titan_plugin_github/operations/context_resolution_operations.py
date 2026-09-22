"""Operations for resolving bounded review context from a focused review plan."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from titan_cli.core.logging import get_logger

from ..managers.diff_context_manager import DiffContextManager, get_or_create_diff_manager
from .prompt_formatting_operations import extract_pr_intent_line
from ..managers.prompt_budget_manager import get_prompt_budget_manager
from ..models.review_enums import AttentionTier, ContextRequestType, FileReadMode
from ..models.review_models import (
    ChangeManifest,
    CommentContextEntry,
    ContextRequest,
    FileContextEntry,
    FileReviewPlan,
    FocusContextBatch,
    ReviewChecklistItem,
    ReviewContextPackage,
    ReviewPlan,
    ReviewBudget,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class FileReadAccess:
    """
    Whether files read from a directory can be trusted to be the PR's head revision.

    Attributes:
        allowed: True when reading files from ``root`` yields the code the diff
                 describes. False means only diff hunks may be used.
        source: Where the trusted content comes from — "worktree", "checkout",
                or "none" when reads are not allowed.
        reason: Short explanation, shown in the UI and logged.
    """
    allowed: bool
    source: str
    reason: str


def resolve_file_read_access(
    worktree_path: Optional[str],
    head_sha: Optional[str] = None,
    checkout_sha: Optional[str] = None,
    checkout_dirty: Optional[bool] = None,
) -> FileReadAccess:
    """
    Decide whether file content on disk may be used as this PR's code.

    A dedicated worktree is checked out at the PR head, so it is always trusted. Without
    one, the only directory available is the user's own checkout, which sits on whatever
    branch they happen to be on. Reading a file from there and pairing it with the PR's
    diff silently mixes two revisions: line numbers stop matching the hunks, and the AI
    reviews code that is not in the PR at all. So the checkout is trusted only when it is
    provably at the head commit with nothing modified on top.

    Args:
        worktree_path: Path to a worktree created for this PR, if any
        head_sha: The PR head commit SHA the diff was computed against
        checkout_sha: HEAD of the user's checkout
        checkout_dirty: Whether the user's checkout has uncommitted changes

    Returns:
        FileReadAccess with the verdict and a reason for display
    """
    if worktree_path:
        return FileReadAccess(True, "worktree", f"worktree at PR head: {worktree_path}")

    if not head_sha or not checkout_sha:
        return FileReadAccess(
            False, "none", "no worktree and the checkout revision could not be verified"
        )

    if checkout_sha != head_sha:
        return FileReadAccess(
            False,
            "none",
            f"checkout is at {checkout_sha[:8]}, PR head is {head_sha[:8]}",
        )

    if checkout_dirty or checkout_dirty is None:
        return FileReadAccess(
            False,
            "none",
            "checkout is at the PR head but has uncommitted changes"
            if checkout_dirty
            else "checkout is at the PR head but its dirty state could not be verified",
        )

    return FileReadAccess(True, "checkout", f"checkout verified at PR head {head_sha[:8]}")


def extract_hunks_only(
    diff: str,
    path: str,
    diff_manager: Optional[DiffContextManager] = None,
) -> list[str]:
    manager = diff_manager or DiffContextManager.from_diff(diff)
    return manager.get_hunk_texts(path)


def extract_expanded_hunks(
    diff: str,
    path: str,
    cwd: Optional[str] = None,
    diff_manager: Optional[DiffContextManager] = None,
) -> list[str]:
    file_content = read_file_content(path, cwd)
    if not file_content:
        return extract_hunks_only(diff, path, diff_manager=diff_manager)

    manager = diff_manager or DiffContextManager.from_diff(diff)
    return manager.build_expanded_hunks(path, file_content, extra_lines=10)


def read_file_content(path: str, cwd: Optional[str] = None) -> Optional[str]:
    try:
        base = Path(cwd) if cwd else Path.cwd()
        file_path = base / path
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError) as e:
        logger.debug("file_read_failed", path=path, error=str(e))
    return None


def _find_related_tests(path: str, cwd: Optional[str] = None) -> Optional[tuple[str, str]]:
    """Return (path, content) for the first existing test file of `path`, or None."""
    p = Path(path)
    stem = p.stem
    candidates = [
        p.parent / "tests" / f"test_{stem}{p.suffix}",
        p.parent / f"test_{stem}{p.suffix}",
        p.parent / f"{stem}_test{p.suffix}",
        Path("tests") / f"test_{stem}{p.suffix}",
        Path("tests") / p.parent / f"test_{stem}{p.suffix}",
    ]

    for candidate in candidates:
        content = read_file_content(str(candidate), cwd)
        if content:
            return str(candidate), content
    return None


def _find_related_context(path: str, cwd: Optional[str] = None) -> Optional[tuple[str, str]]:
    """Return (path, content) for the first existing sibling of `path`, or None."""
    p = Path(path)
    candidates = [
        p.parent / "__init__.py",
        p.parent / "protocols.py",
        p.parent / "interfaces.py",
        p.parent / f"base_{p.stem}{p.suffix}",
        p.parent / f"{p.stem}_base{p.suffix}",
    ]

    for candidate in candidates:
        if candidate == p:
            continue
        content = read_file_content(str(candidate), cwd)
        if content:
            return str(candidate), content[:3000]
    return None


def resolve_context_requests(
    requests: list[ContextRequest],
    cwd: Optional[str] = None,
    allow_file_reads: bool = True,
) -> dict[str, str]:
    """
    Resolve extra context requests by reading sibling files.

    Returns nothing when ``allow_file_reads`` is False: these files are read whole from
    disk, so an unverified revision would put unrelated code in the prompt.
    """
    if not allow_file_reads:
        return {}

    result: dict[str, str] = {}
    for req in requests:
        found = (
            _find_related_tests(req.for_path, cwd)
            if req.type == ContextRequestType.RELATED_TESTS
            else _find_related_context(req.for_path, cwd)
        )
        if not found:
            continue
        found_path, content = found
        key = f"{req.type}:{req.for_path}"
        # Reaching this point means the working tree is readable, so the session can open
        # the sibling itself. Naming it costs a line where pasting it cost up to 2,000
        # chars of the content budget -- charged to EVERY batch, since related context
        # ships with all of them, and then stripped again by the first degradation to make
        # the call fit. The path plus the reason is the part the model could not guess.
        result[key] = f"Open `{found_path}` in the working tree if this file's review needs it."
    return result


DEEP_BATCH_ID = "deep_1"
"""The deep session's batch id. One per review; overflow splits append a/b as usual."""

# The floor under one file's inline diff share. Below this an inline diff is too small to
# be worth anchoring against, so the file is better handed over as a reference the session
# opens itself than as a truncated fragment.
MIN_INLINE_DIFF_CHARS = 4000


def _inline_diff_allowance(content_budget: int, file_count: int) -> int:
    """How much of ONE file's diff may travel inline in the deep batch.

    The deep batch holds every deep file, so the budget is shared rather than spent by
    whoever comes first. A file over its share keeps its reference and hunk headers and
    drops the inline diff.
    """
    if file_count <= 0:
        return content_budget
    return max(MIN_INLINE_DIFF_CHARS, content_budget // file_count)


PR_INTENT_MAX_CHARS = 1200
"""How much of the PR description the reviewing session is handed.

Six times the 200-char line a per-file batch got, because a batch that judges the change
against its stated intent needs the claim, not a summary of it. Still capped: a PR
description can run to a novel, and the review is not a reading exercise. Characters are
the wrong unit for this tier anyway (D-002) -- the cap is about focus, not cost.
"""


def build_review_context_package(
    plan: ReviewPlan,
    diff: str,
    manifest: ChangeManifest,
    checklist: list[ReviewChecklistItem],
    comment_context: list[CommentContextEntry],
    budget: ReviewBudget,
    cwd: Optional[str] = None,
    diff_manager: Optional[DiffContextManager] = None,
    allow_file_reads: bool = True,
    attention_plan=None,
    review_profile=None,
    scan_suspicions: Optional[list[dict]] = None,
) -> ReviewContextPackage:
    """
    Build the batched review context package for the AI prompt.

    When ``allow_file_reads`` is False, no file is read from ``cwd``: every file falls
    back to its diff hunks. Callers set this when the content on disk cannot be proven to
    be the PR's head revision — see ``resolve_file_read_access``.

    ``attention_plan``, when given, puts the shape of the WHOLE change on every batch —
    one content-free line per changed file with its role and tier. Without it a batch can
    only report what it sees in the files it was handed, which is what made the
    cross-file and missing-piece questions unanswerable.
    """
    manager = diff_manager or get_or_create_diff_manager(diff)
    applicable_ids = set(plan.review_axes)
    checklist_applicable = [item for item in checklist if item.id in applicable_ids] or checklist[:2]

    if len(plan.extra_context_requests) > 1:
        logger.info(
            "extra_context_requests_trimmed",
            planned=len(plan.extra_context_requests),
            kept=1,
            dropped=len(plan.extra_context_requests) - 1,
        )

    related_files = resolve_context_requests(
        plan.extra_context_requests[:1], cwd, allow_file_reads=allow_file_reads
    )
    comment_context = comment_context[: budget.max_comment_entries]
    content_budget = get_prompt_budget_manager().content_budget(budget)


    # More than the one-line cap a per-file batch got: this batch judges the change
    # against what the PR says it does, so it needs the claim in full. Still capped —
    # a PR description can be a novel, and the review is not a reading exercise.
    pr_intent = (
        extract_pr_intent_line(manifest.pr.description, max_chars=PR_INTENT_MAX_CHARS)
        if manifest.pr
        else None
    )

    # The deep session reads the DEEP files and nothing else. Until now `focus_files`
    # came straight from the scorer (top N candidates), so a file the attention plan had
    # tiered `glance` or `skip` could still be deep-read: on PR 251,
    # `docs/concepts/oauth-manager.md` was tiered skip and went into a review batch anyway.
    # That made the tiers decoration. Files left out here are not lost -- they are
    # declared, on screen and in the log, and the skim (call 1) is what looks at the
    # glance ones.
    focus_files = plan.focus_files
    if attention_plan is not None:
        deep_paths = set(attention_plan.paths_for(AttentionTier.DEEP))
        focus_files = [file_plan for file_plan in plan.focus_files if file_plan.path in deep_paths]
        excluded = [
            file_plan.path for file_plan in plan.focus_files if file_plan.path not in deep_paths
        ]
        if excluded:
            logger.info(
                "focus_files_outside_deep_tier",
                dropped=len(excluded),
                kept=len(focus_files),
                paths=sorted(excluded),
            )

    context_docs = resolve_context_docs(
        review_profile.context_docs if review_profile else [],
        cwd,
        review_profile.max_context_docs if review_profile else 0,
        allow_file_reads=allow_file_reads,
    )

    change_shape: list[str] = []
    if attention_plan is not None:
        from .attention_operations import build_change_shape_lines

        # Marked from the files that will ACTUALLY be read, not from the tier: a deep file
        # the scorer never selected must not be described to the model as reviewed here.
        change_shape = build_change_shape_lines(
            attention_plan, manifest.files, {file_plan.path for file_plan in focus_files}
        )

    # ONE deep batch, built from the tier rather than emerging from a character budget.
    #
    # This function used to be a packer: it walked the focus files, added each one's
    # estimated size to a running total and started a new batch whenever the total crossed
    # the content budget. That made the number of AI calls an accident of how large the
    # files happened to be -- nine deep files became seven calls on PR 251 -- and it made
    # the attention tiers decoration, since the thing that actually decided the work was
    # a character sum. The tiers decide now: the deep files are one session, the glance
    # files are the skim's business, and the character budget is only an emergency valve
    # (`fit_batch_to_budget`, plus cov-013's split when a call expires).
    #
    # What the budget still decides is how much of each file's DIFF travels inline. The
    # session can open any of these files from the working tree, so a file whose diff
    # exceeds its share of the budget keeps its reference and its hunk headers and loses
    # the inline diff -- weaker anchoring for that one file, not a lost file.
    inline_allowance = _inline_diff_allowance(content_budget, len(focus_files))
    deep_files: dict[str, FileContextEntry] = {}
    deep_chars = _estimate_related_chars(related_files) + _estimate_comment_chars(comment_context)
    for file_plan in focus_files:
        entry = _resolve_file_context(
            file_plan,
            diff,
            budget,
            cwd,
            manager,
            allow_file_reads=allow_file_reads,
            inline_diff_allowance=inline_allowance,
        )
        deep_files[file_plan.path] = entry
        deep_chars += entry.approximate_chars or get_prompt_budget_manager().estimate_entry_chars(entry)

    batches: list[FocusContextBatch] = []
    if deep_files:
        logger.info(
            "deep_batch_built",
            files=len(deep_files),
            inline_diff_allowance=inline_allowance,
            approximate_chars=deep_chars,
            prompt_budget_target_chars=budget.deep_max_prompt_chars,
            inline_diff_files=sum(1 for entry in deep_files.values() if entry.hunks),
            reference_only_files=sum(
                1 for entry in deep_files.values() if entry.worktree_reference and not entry.hunks
            ),
        )
        batches.append(
            FocusContextBatch(
                batch_id=DEEP_BATCH_ID,
                tier=AttentionTier.DEEP,
                files_context=deep_files,
                comment_context=comment_context,
                checklist_applicable=checklist_applicable,
                related_files=related_files,
                pr_manifest=manifest.pr,
                change_shape=change_shape,
                context_docs=context_docs,
                scan_suspicions=list(scan_suspicions or []),
                pr_intent=pr_intent,
                approximate_chars=deep_chars,
                prompt_budget_target_chars=budget.deep_max_prompt_chars,
            )
        )

    return ReviewContextPackage(batches=batches)


def _resolve_file_context(
    file_plan: FileReviewPlan,
    diff: str,
    budget: ReviewBudget,
    cwd: Optional[str] = None,
    diff_manager: Optional[DiffContextManager] = None,
    allow_file_reads: bool = True,
    inline_diff_allowance: Optional[int] = None,
) -> FileContextEntry:
    manager = diff_manager or DiffContextManager.from_diff(diff)
    desired_mode = file_plan.read_mode
    # The model anchors comments inside the hunks it can see; a header it never saw
    # is a region it cannot anchor to, so those comments end up on unpublishable
    # lines and degrade to the general body. 30 covers any realistic file (a header
    # is ~40 chars, so worst case ~1.2k chars) while still bounding pathological diffs.
    hunk_headers = [hunk.header for hunk in manager.get_hunks(file_plan.path)[:30]]
    file_limits = _file_limits(file_plan.path)
    resolved_entry: FileContextEntry | None = None

    if not allow_file_reads and desired_mode in (FileReadMode.FULL_FILE, FileReadMode.EXPANDED_HUNKS):
        # Content on disk is not provably this PR's revision; hunks come from the diff
        # itself and are always correct.
        logger.debug(
            "file_read_not_allowed",
            path=file_plan.path,
            requested_mode=desired_mode,
            applied_mode="hunks_only",
        )
        desired_mode = FileReadMode.HUNKS_ONLY

    if allow_file_reads and desired_mode in (FileReadMode.FULL_FILE, FileReadMode.EXPANDED_HUNKS):
        # The session has the file on disk, so shipping its body in the prompt buys
        # nothing and costs the packing decision. Measured on PR 251: nine deep files
        # resolved to full-file/expanded-hunk bodies filled the content budget and spilled
        # into SEVEN batches, and Phase 1 then degraded almost every one of them back to a
        # worktree reference to fit the call -- context added and then taken away, with the
        # batch count already decided on the size it no longer had.
        #
        # What stays inline is the DIFF: the model cannot get "what changed here" from the
        # working tree (it has the post-change file, and Bash is disallowed), and the added
        # lines are the anchor material every inline comment needs.
        hunks = manager.get_hunk_texts(file_plan.path)
        hunks_chars = sum(len(hunk) for hunk in hunks)
        # The allowance is this file's share of the deep batch's budget, not a per-file
        # constant: the batch holds every deep file, so the first big file must not spend
        # what the rest need. Over its share, the file travels as a reference.
        allowance = inline_diff_allowance if inline_diff_allowance is not None else file_limits["max_file_chars"]
        if hunks and hunks_chars <= allowance:
            resolved_entry = FileContextEntry(
                path=file_plan.path,
                read_mode=FileReadMode.WORKTREE_REFERENCE,
                worktree_reference=True,
                hunks=hunks,
                review_hint=_build_worktree_hint(file_plan),
                changed_hunk_headers=hunk_headers,
                approximate_chars=(
                    hunks_chars + get_prompt_budget_manager().WORKTREE_REFERENCE_PROMPT_CHARS
                ),
            )
            return _log_file_context(resolved_entry, file_plan.path)

    if desired_mode == FileReadMode.FULL_FILE:
        content = read_file_content(file_plan.path, cwd)
        if content and len(content) <= file_limits["max_file_chars"] and len(content.splitlines()) <= file_limits["max_file_lines"]:
            resolved_entry = FileContextEntry(
                path=file_plan.path,
                read_mode=FileReadMode.FULL_FILE,
                full_content=content,
                changed_hunk_headers=hunk_headers,
                approximate_chars=len(content),
            )
            return _log_file_context(resolved_entry, file_plan.path)
        desired_mode = FileReadMode.EXPANDED_HUNKS

    if desired_mode == FileReadMode.EXPANDED_HUNKS:
        file_content = read_file_content(file_plan.path, cwd)
        expanded = (
            manager.build_expanded_hunks(
                file_plan.path,
                file_content,
                extra_lines=file_limits["extra_lines"],
            )
            if file_content
            else manager.get_hunk_texts(file_plan.path)
        )
        expanded_chars = sum(len(hunk) for hunk in expanded)
        if expanded and expanded_chars <= file_limits["max_file_chars"]:
            resolved_entry = FileContextEntry(
                path=file_plan.path,
                read_mode=FileReadMode.EXPANDED_HUNKS,
                expanded_hunks=expanded,
                changed_hunk_headers=hunk_headers,
                approximate_chars=expanded_chars,
            )
            return _log_file_context(resolved_entry, file_plan.path)
        desired_mode = FileReadMode.HUNKS_ONLY

    if desired_mode == FileReadMode.HUNKS_ONLY:
        hunks = manager.get_hunk_texts(file_plan.path)
        hunks_chars = sum(len(hunk) for hunk in hunks)
        if hunks and (hunks_chars <= file_limits["max_file_chars"] or not allow_file_reads):
            # Over-budget hunks are still preferable to the worktree_reference fallback
            # when reads are not allowed: that mode has the CLI open the file itself, which
            # is the same wrong-revision read, just delegated. The batching loop keeps the
            # prompt bounded via approximate_chars.
            resolved_entry = FileContextEntry(
                path=file_plan.path,
                read_mode=FileReadMode.HUNKS_ONLY,
                hunks=hunks,
                changed_hunk_headers=hunk_headers,
                approximate_chars=hunks_chars,
            )
            return _log_file_context(resolved_entry, file_plan.path)

    if not allow_file_reads:
        # No hunks and no trustworthy file to read: headers only, so the AI still knows
        # the file changed but is never handed content from another revision.
        resolved_entry = FileContextEntry(
            path=file_plan.path,
            read_mode=FileReadMode.HUNKS_ONLY,
            changed_hunk_headers=hunk_headers,
            review_hint=(
                "File content unavailable: no PR worktree and the local checkout is not "
                "at this PR's head commit. Review from the diff only."
            ),
        )
        return _log_file_context(resolved_entry, file_plan.path)

    resolved_entry = FileContextEntry(
        path=file_plan.path,
        read_mode=FileReadMode.WORKTREE_REFERENCE,
        worktree_reference=True,
        review_hint=_build_worktree_hint(file_plan),
        changed_hunk_headers=hunk_headers,
        approximate_chars=get_prompt_budget_manager().WORKTREE_REFERENCE_PROMPT_CHARS,
    )
    return _log_file_context(resolved_entry, file_plan.path)


def _file_limits(path: str) -> dict[str, int]:
    """How much of one file a deep batch may carry.

    One set of limits, not four. The old version shrank every file when the PR was
    classified LARGE or HUGE, which made sense when a big PR meant more focus files; the
    deep tier is now capped at a fixed number of sessions, so the PR's overall size no
    longer says anything about how much room one file has. `fit_batch_to_budget` still
    shrinks a batch that overflows, so the generous limits are safe.

    The per-path branches went with it: they hinged on a hardcoded list of filename
    tokens (`viewmodel`, `manager`, `service`, ...), which is a guess about one kind of
    codebase living in code that has to work for any of them. What a project considers
    central belongs in its own profile.
    """
    return {
        "max_file_chars": 14000,
        "max_file_lines": 260,
        "extra_lines": 8,
    }


def _build_worktree_hint(file_plan: FileReviewPlan) -> str:
    reasons = "; ".join(file_plan.reasons[:2]) if file_plan.reasons else "central changed file"
    return (
        "Read this file from the worktree. Prioritize the changed regions first and validate: "
        f"{reasons}. Check especially for semantic mismatches, missing guarantees, state inconsistencies, "
        "and behavior changes that remain executable but no longer mean the same thing. You may check a few "
        "directly related files (an imported type, a caller, a test) if genuinely needed to resolve a "
        "specific doubt, but do not perform a broad, open-ended exploration of the codebase."
    )


def _estimate_related_chars(related_files: dict[str, str]) -> int:
    return sum(len(label) + len(content[:2000]) for label, content in related_files.items())


def _estimate_comment_chars(comment_context: list[CommentContextEntry]) -> int:
    return sum(len(entry.title) + len(entry.summary) for entry in comment_context)


def _log_file_context(entry: FileContextEntry, path: str) -> FileContextEntry:
    logger.debug(
        "file_context_resolved",
        path=path,
        read_mode=entry.read_mode,
        chars=entry.approximate_chars,
        changed_hunks=len(entry.changed_hunk_headers),
        worktree_reference=entry.worktree_reference,
        trimmed=entry.read_mode == FileReadMode.WORKTREE_REFERENCE,
    )
    return entry


def resolve_context_docs(
    patterns: list[str],
    cwd: Optional[str],
    limit: int,
    allow_file_reads: bool = True,
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

    Nothing is offered when ``allow_file_reads`` is False: pointing the model at a file
    on disk is the same wrong-revision read as pasting it.
    """
    if not allow_file_reads or not cwd or limit <= 0 or not patterns:
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
