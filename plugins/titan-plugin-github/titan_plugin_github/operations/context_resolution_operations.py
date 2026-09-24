"""Operations for resolving bounded review context from a focused review plan."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from titan_cli.core.logging import get_logger

from ..managers.diff_context_manager import DiffContextManager, get_or_create_diff_manager
from .prompt_formatting_operations import review_pr_description
from ..managers.prompt_budget_manager import get_prompt_budget_manager
from ..models.review_enums import AttentionTier, FileReadMode
from ..models.review_models import (
    ChangeManifest,
    CommentContextEntry,
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
        return FileReadAccess(
            True, "worktree", f"worktree at PR head: .../{Path(worktree_path).name}"
        )

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


DEEP_BATCH_ID = "deep_1"
"""The one deep session of a review.

Singular by design (D-014): the session is the unit of understanding, so a prompt that
does not fit loses diff detail per file, never gains a second session. A budget-driven
split (`fit_batch_to_budget`) can still append a/b as an emergency, and that is a failure
worth noticing rather than a routine path.
"""

# The floor under one file's inline diff share. Below this an inline diff is too small to
# be worth anchoring against, so the file is better handed over as a reference the session
# opens itself than as a truncated fragment.
MIN_INLINE_DIFF_CHARS = 4000


def _flagged_file_entries(suspicions: list[dict], already_present: set[str], manager) -> dict:
    """Header-only entries for the files the first pass flagged.

    Their diffs are deliberately absent: the triage read them already, and resending them
    would both pay twice and invite a full review of a file nobody tiered as worth one.
    The headers stay because the working tree holds the file AFTER the change, so without
    them the session cannot tell which lines an inline comment may attach to.
    """
    entries: dict[str, FileContextEntry] = {}
    for suspicion in suspicions:
        path = (suspicion.get("path") or "").strip()
        if not path or path in already_present or path in entries:
            continue
        entries[path] = FileContextEntry(
            path=path,
            read_mode=FileReadMode.WORKTREE_REFERENCE,
            worktree_reference=True,
            changed_hunk_headers=[hunk.header for hunk in manager.get_hunks(path)[:30]],
            review_hint="Flagged by the triage — settle its question after the review; do not go looking for more.",
            approximate_chars=get_prompt_budget_manager().WORKTREE_REFERENCE_PROMPT_CHARS,
        )
    return entries


def _measure_prompt(
    files_context,
    comment_context,
    checklist_applicable,
    related_files,
    manifest,
    change_shape,
    context_docs,
    suspicions,
    pr_intent,
    diff,
    manager,
) -> str:
    """The prompt this session would send, measured rather than estimated.

    Estimating is what produced the ceilings this domain spent two days deleting: a
    number that stands in for a size is a policy in disguise. The real string is cheap to
    build and exact.
    """
    from ..models.review_models import FocusContextBatch
    from .findings_operations import build_findings_prompt_parts

    probe = FocusContextBatch(
        batch_id=DEEP_BATCH_ID,
        tier=AttentionTier.DEEP,
        files_context={
            **files_context,
            **_flagged_file_entries(suspicions, set(files_context), manager),
        },
        comment_context=comment_context,
        checklist_applicable=checklist_applicable,
        related_files=related_files,
        pr_manifest=manifest.pr,
        change_shape=change_shape,
        context_docs=context_docs,
        triage_suspicions=suspicions,
        pr_intent=pr_intent,
    )
    return build_findings_prompt_parts(probe)["prompt"]


def _inline_diff_allowance(content_budget: int, file_count: int) -> int:
    """How much of ONE file's diff may travel inline in the deep batch.

    The deep batch holds every deep file, so the budget is shared rather than spent by
    whoever comes first. A file over its share keeps its reference and hunk headers and
    drops the inline diff.
    """
    if file_count <= 0:
        return content_budget
    return max(MIN_INLINE_DIFF_CHARS, content_budget // file_count)


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
    triage_suspicions: Optional[list[dict]] = None,
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
    # Falling back to EVERY offered axis, not two of them: reaching here means the plan
    # selected no axis at all, which is an upstream failure, and the safe direction is to
    # ask about everything the project declared rather than about almost nothing.
    checklist_applicable = [item for item in checklist if item.id in applicable_ids] or list(checklist)

    # Sibling files used to be pasted in on request from the AI planning call; that call
    # is gone and the session opens whatever it needs from the working tree itself.
    related_files: dict[str, str] = {}
    comment_context = comment_context[: budget.max_comment_entries]
    content_budget = get_prompt_budget_manager().content_budget(budget)


    # More than the one-line cap a per-file batch got: this batch judges the change
    # against what the PR says it does, so it needs the claim in full. Still capped —
    # a PR description can be a novel, and the review is not a reading exercise.
    pr_intent = review_pr_description(manifest.pr.description) if manifest.pr else None

    # The deep session reads the DEEP files and nothing else. Until now `focus_files`
    # came straight from the scorer (top N candidates), so a file the attention plan had
    # tiered `glance` or `skip` could still be deep-read: on PR 251,
    # `docs/concepts/oauth-manager.md` was tiered skip and went into a review batch anyway.
    # That made the tiers decoration. Files left out here are not lost -- they are
    # declared, on screen and in the log, and the triage (call 1) is what looks at the
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

        # Marked from the files ACTUALLY read: a deep file the scorer never selected must
        # not be described to the model as reviewed. There is no "read by another pass"
        # label any more, because there is no other pass.
        change_shape = build_change_shape_lines(
            attention_plan, manifest.files, {file_plan.path for file_plan in focus_files}
        )

    # ONE session over every deep file. Not a batch of them -- the session is the unit of
    # understanding, and what it understands about one file is what lets it see the defect
    # that spans two (D-014).
    #
    # This function has been three things. It was a packer, where the number of AI calls
    # was an accident of file size (nine deep files became seven calls on PR 251). Then it
    # chunked by a constant, `DEEP_FILES_PER_SESSION = 12`, which split ragnarok PR 3685's
    # 24 deep files into two sessions although they amount to ~53k chars against a
    # 120,000 ceiling -- paying twice for the manifest, the context documents, the
    # checklist and the comment context to obtain two sessions that could not talk to each
    # other, while the best findings this domain has produced were cross-file ones.
    #
    # What adjusts when the prompt does not fit is the INLINE DIFF PER FILE, never the
    # session: a file over its allowance keeps its reference and its hunk headers and the
    # session opens it from the working tree. Fidelity degrades; understanding does not
    # divide.
    # What adjusts when the prompt does not fit is which files carry their diff INLINE,
    # never whether they are in the session: a file demoted to reference keeps its hunk
    # headers and the session opens it from the working tree. Fidelity degrades;
    # understanding does not divide.
    #
    # And it degrades from the BOTTOM of the ranking. An earlier version lowered a single
    # allowance for everyone, which meant the file that lost its diff was whichever
    # happened to be large -- so a big central file degraded before a small trivial one.
    # `focus_files` arrives in the scorer's order, so the least important file gives up
    # its diff first and the core keeps it until last.
    #
    # What a demoted file loses is real but narrow: the literal added lines the model
    # copies its `snippet` from, which is what inline anchoring depends on (D-008). It
    # does not lose the review.
    suspicions = list(triage_suspicions or [])
    inline_allowance = _inline_diff_allowance(content_budget, len(focus_files))
    files_context: dict[str, FileContextEntry] = {}
    prompt_chars = 0
    demoted: list[str] = []

    def _resolve(file_plan, allowance: int) -> FileContextEntry:
        return _resolve_file_context(
            file_plan,
            diff,
            budget,
            cwd,
            manager,
            allow_file_reads=allow_file_reads,
            inline_diff_allowance=allowance,
        )

    def _measure(context: dict) -> int:
        return len(
            _measure_prompt(
                context,
                comment_context,
                checklist_applicable,
                related_files,
                manifest,
                change_shape,
                context_docs,
                suspicions,
                pr_intent,
                diff,
                manager,
            )
        )

    files_context = {file_plan.path: _resolve(file_plan, inline_allowance) for file_plan in focus_files}
    if files_context:
        prompt_chars = _measure(files_context)
        # The even share is a starting point, not a verdict. A file whose diff is larger
        # than its share -- often the central one -- starts as a bare reference; when the
        # session still has room, it gets its diff back, in plan order, as long as the
        # real prompt fits. On ragnarok PR #3692 the even share left 7 of 27 files without
        # their diff in a prompt using 65k of 120k.
        restored: list[str] = []
        for file_plan in focus_files:
            entry = files_context[file_plan.path]
            if (entry.hunks and not entry.removals_only) or not entry.worktree_reference:
                continue
            # The full diff first; failing that, its removed lines -- the part the
            # session cannot recover from the tree. On ragnarok PR #3720 the central
            # file's removals (12,985 chars) exceeded its even share (~8,900) and this
            # pass only ever tried the full diff, so it went bare and the session
            # dismissed the defect it could not see.
            full = _resolve(file_plan, budget.deep_max_prompt_chars)
            removals = (
                None
                if entry.removals_only
                else _removals_only_entry(file_plan, manager.get_hunk_texts(file_plan.path), entry.changed_hunk_headers)
            )
            for candidate in (full, removals):
                if candidate is None or not candidate.hunks:
                    continue
                trial = {**files_context, file_plan.path: candidate}
                trial_chars = _measure(trial)
                if trial_chars <= budget.deep_max_prompt_chars:
                    files_context, prompt_chars = trial, trial_chars
                    restored.append(file_plan.path)
                    break
        if restored:
            logger.debug("deep_session_diffs_restored", files=len(restored), paths=restored)
        # Least important first, which is the tail of the scorer's ranking.
        for file_plan in reversed(focus_files):
            if prompt_chars <= budget.deep_max_prompt_chars:
                break
            entry = files_context.get(file_plan.path)
            if entry is None or not entry.hunks:
                continue  # already a reference; nothing left to give up
            files_context[file_plan.path] = _resolve(file_plan, 0)
            demoted.append(file_plan.path)
            prompt_chars = _measure(files_context)

        if demoted:
            logger.info(
                "deep_session_fidelity_reduced",
                demoted_to_reference=len(demoted),
                paths=demoted,
                prompt_actual_chars=prompt_chars,
                prompt_budget_target_chars=budget.deep_max_prompt_chars,
                still_over_budget=prompt_chars > budget.deep_max_prompt_chars,
            )

    batches: list[FocusContextBatch] = []
    if files_context or suspicions:
        # Flagged files join the SAME session as a second task list: headers and the
        # question, never their diff, which the triage already read.
        files_context.update(
            _flagged_file_entries(suspicions, set(files_context), manager)
        )
        logger.info(
            "deep_session_built",
            files=len(focus_files),
            flagged_files=len(files_context) - len(focus_files),
            suspicions=len(suspicions),
            inline_diff_allowance=inline_allowance,
            prompt_actual_chars=prompt_chars,
            prompt_budget_target_chars=budget.deep_max_prompt_chars,
            inline_diff_files=sum(1 for entry in files_context.values() if entry.hunks and not entry.removals_only),
            removals_only_files=sum(1 for entry in files_context.values() if entry.removals_only),
            reference_only_files=sum(
                1 for entry in files_context.values() if entry.worktree_reference and not entry.hunks
            ),
        )
        batches.append(
            FocusContextBatch(
                batch_id=DEEP_BATCH_ID,
                tier=AttentionTier.DEEP,
                files_context=files_context,
                comment_context=comment_context,
                checklist_applicable=checklist_applicable,
                related_files=related_files,
                pr_manifest=manifest.pr,
                change_shape=change_shape,
                context_docs=context_docs,
                triage_suspicions=suspicions,
                pr_intent=pr_intent,
                approximate_chars=prompt_chars,
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

    # This file's share of the session's inline budget. The caller lowers it to demote a
    # file to a reference when the prompt does not fit.
    allowance = (
        inline_diff_allowance if inline_diff_allowance is not None else file_limits["max_file_chars"]
    )

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
        # Over its share, the diff is cut down to its REMOVED lines: the session opens the
        # file for everything added or kept, but what was deleted exists nowhere it can
        # reach (Bash, so git, is disallowed). On ragnarok PR #3720 the central
        # AnalyticsStore.kt (32,495 chars of diff) went as a bare reference, the session
        # searched the post-change tree for two deleted reducers, found "none", and
        # dismissed the question that would have found them -- at $2.17 of searching. Its
        # removed lines are 12,985 chars.
        removals_entry = _removals_only_entry(file_plan, hunks, hunk_headers)
        if removals_entry and removals_entry.approximate_chars <= allowance:
            return _log_file_context(removals_entry, file_plan.path)
        # Not even the removals fit: a reference with its hunk headers, and the session
        # opens the file. This used to fall through to the expanded-hunks branch below, which
        # ignores the allowance -- so "demoting" a file made its entry LARGER, and on
        # ragnarok PR #3692 all 27 deep files were "demoted" and the session still came
        # out at 122,319 chars and was split in two. It never showed while a scorer
        # handed low-score files `hunks_only`, the one mode the allowance did govern.
        return _log_file_context(
            FileContextEntry(
                path=file_plan.path,
                read_mode=FileReadMode.WORKTREE_REFERENCE,
                worktree_reference=True,
                review_hint=_build_worktree_hint(file_plan),
                changed_hunk_headers=hunk_headers,
                approximate_chars=get_prompt_budget_manager().WORKTREE_REFERENCE_PROMPT_CHARS,
            ),
            file_plan.path,
        )

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
        # The session's allowance governs here too, not just the richer read modes: a
        # file planned as hunks_only was otherwise immune to demotion, so lowering the
        # allowance moved nothing. When reads are NOT allowed the hunks stay whatever
        # their size, because the diff is then the only honest thing to send.
        hunks_cap = allowance if allow_file_reads else file_limits["max_file_chars"]
        if hunks and (hunks_chars <= hunks_cap or not allow_file_reads):
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


REMOVALS_ONLY_HINT = (
    " Only the REMOVED lines of this file's diff are shown below: open the file for what was"
    " added or kept. What was removed is not in the working tree any more, so check here"
    " whether anything it did is now missing."
)


def _removals_only_entry(
    file_plan: FileReviewPlan, hunks: list[str], hunk_headers: list[str]
) -> Optional[FileContextEntry]:
    """A reference carrying only the removed lines of its diff, or None if nothing was removed."""
    removals = _removed_lines_only(hunks)
    if not removals:
        return None
    return FileContextEntry(
        path=file_plan.path,
        read_mode=FileReadMode.WORKTREE_REFERENCE,
        worktree_reference=True,
        hunks=removals,
        removals_only=True,
        review_hint=_build_worktree_hint(file_plan) + REMOVALS_ONLY_HINT,
        changed_hunk_headers=hunk_headers,
        approximate_chars=(
            sum(len(hunk) for hunk in removals) + get_prompt_budget_manager().WORKTREE_REFERENCE_PROMPT_CHARS
        ),
    )


def _removed_lines_only(hunks: list[str]) -> list[str]:
    """Each hunk reduced to its header and its removed lines; hunks that remove nothing drop out."""
    reduced: list[str] = []
    for hunk in hunks:
        lines = hunk.splitlines()
        if not lines:
            continue
        header, body = lines[0], lines[1:]
        removed = [line for line in body if line.startswith("-") and not line.startswith("---")]
        if removed:
            reduced.append("\n".join([header, *removed]) + "\n")
    return reduced


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


# How a file reaches the deep session, in the order they are listed on screen.
CONTEXT_GROUP_LABELS = {
    "inline": "Diff in the prompt, file open in the worktree",
    "removals_only": "Only the removed lines (the rest did not fit)",
    "reference": "Named for a triage question, opened on demand",
    "named": "Named only",
}


def group_batch_files_by_delivery(batch: FocusContextBatch) -> dict[str, list[str]]:
    """Every file of a batch under how the session receives it, empty groups left out.

    The same classification `deep_session_built` counts, so the screen and the log
    agree: a file with hunks (not removals-only) is inline, a removals-only file lost
    its added lines to the budget, and a worktree reference with no hunks is a file the
    session was pointed at -- a triage question -- rather than handed.
    """
    groups: dict[str, list[str]] = {key: [] for key in CONTEXT_GROUP_LABELS}
    for path, entry in batch.files_context.items():
        if entry.removals_only:
            groups["removals_only"].append(path)
        elif entry.hunks:
            groups["inline"].append(path)
        elif entry.worktree_reference:
            groups["reference"].append(path)
        else:
            groups["named"].append(path)
    return {key: paths for key, paths in groups.items() if paths}
