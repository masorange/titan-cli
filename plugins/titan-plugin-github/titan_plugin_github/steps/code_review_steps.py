"""
Steps for AI-powered PR code review.

This module contains steps for reviewing pull requests authored by others using
AI analysis combined with project-specific skill guidelines.
"""
import os
from pathlib import Path
import re
import threading
import time
from difflib import SequenceMatcher
from typing import Callable, List, Optional, Tuple

from titan_cli.ai.router.declaration import declare_ai_usage
from titan_cli.ai.router.enums import AIProviderType, AITask
from titan_cli.ai.router.resolver import AIRouteNeedsInput
from titan_cli.core.logging import get_logger
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Exit, Skip
from titan_cli.core.interrupt import run_interruptible
from titan_cli.core.result import ClientSuccess, ClientError
from titan_cli.external_cli.adapters import get_headless_adapter, list_available_headless_clis
from titan_cli.ui.tui.widgets import ChoiceOption, OptionItem, PromptChoice

from ..managers.diff_context_manager import get_or_create_diff_manager
from ..models.review_enums import ReviewActionType, ThreadDecisionType
from ..models.review_models import (
    ReferencedCommitContext,
    ReviewActionProposal,
)
from ..models.view import UICommentThread, UIPullRequest
from ..operations.ai_cost_operations import (
    AICallRecord,
    format_cost_summary,
    summarize_ai_calls,
)
from ..operations.ai_response_parsing_operations import (
    REFORMAT_RETRY_TIMEOUT_SECONDS,
    build_json_reformat_prompt,
    extract_json_payload,
)
from ..operations.code_review_operations import (
    select_files_for_review,
    compute_diff_stat,
)
from ..operations.review_action_operations import (
    build_new_comment_actions as build_new_comment_actions_operation,
    build_review_action_payload,
    classify_github_review_rejection,
    extract_diff_hunk_for_action,
    extract_file_excerpt_for_action,
    resolve_action_anchors,
)
from ..operations.worktree_operations import review_base_ref, review_head_ref
from ..operations.thread_resolution_operations import (
    batch_thread_review_contexts,
    build_thread_review_candidates as build_thread_review_candidates_operation,
    build_thread_review_contexts as build_thread_review_contexts_operation,
    build_thread_resolution_prompt,
    build_thread_actions as build_thread_actions_operation,
)
from ..operations.pr_selection_operations import (
    build_pr_selection_description,
    build_pr_selection_title,
)

from ..operations.manifest_operations import (
    build_change_manifest as build_change_manifest_operation,
)

from ..operations.manifest_operations import (
        build_existing_comments_index as build_existing_comments_index_operation,
    )

logger = get_logger(__name__)

_PROMPT_PREVIEW_CHARS = 2000
_RESPONSE_PREVIEW_CHARS = 1500

# Writing every prompt and response to disk in full made `ai_prompt_full` +
# `ai_prompt_built` + `ai_response_full` + `ai_response_received` 47.6% of a
# 15 MB rotation set — the single largest thing in the log, and the reason the
# retention window collapsed from months to hours. The bounded previews above
# answer nearly every debugging question; the unbounded dumps are opt-in.
#
# Set TITAN_LOG_AI_PAYLOADS=1 to get them back when a prompt itself is the
# thing under investigation.
def _ai_payload_logging_enabled() -> bool:
    return os.getenv("TITAN_LOG_AI_PAYLOADS", "").strip().lower() in ("1", "true", "yes")
_COMMIT_SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
_CENTRAL_PATH_HINTS = ("/utils/", "/configuration/", "/interceptors/", "/base/", "Utils.kt", "Configuration.kt")
_MAX_REFERENCED_COMMITS_PER_THREAD = 3
_MAX_REFERENCED_COMMIT_FILES = 3
_MAX_REFERENCED_COMMIT_PATCH_CHARS = 4000


def _preview_edges(text: str, limit: int) -> tuple[str, str]:
    """Return start/end previews for large text blobs."""
    if len(text) <= limit:
        return text, text
    return text[:limit], text[-limit:]


def _log_ai_prompt(step_name: str, cli_name: str, prompt: str, **extra) -> None:
    """Log prompt metadata plus previews for review debugging."""
    first, last = _preview_edges(prompt, _PROMPT_PREVIEW_CHARS)
    logger.debug(
        "ai_prompt_built",
        step=step_name,
        cli=cli_name,
        prompt_chars=len(prompt),
        prompt_first_chars=first,
        prompt_last_chars=last,
        **extra,
    )
    if _ai_payload_logging_enabled():
        logger.debug(
            "ai_prompt_full",
            step=step_name,
            cli=cli_name,
            prompt=prompt,
            **extra,
        )


def _log_session_activity(cli_name: str, activity: Optional[dict]) -> None:
    """Record what the review session did, when its CLI reports it.

    The commands go at debug: the counts say how much work happened, the commands say
    which files it was spent on.
    """
    if not activity:
        return
    commands = activity.get("commands", [])
    logger.info(
        "review_session_activity",
        cli=cli_name,
        items=activity.get("items", {}),
        commands=len(commands),
    )
    logger.debug("review_session_commands", cli=cli_name, commands=commands)


def _log_ai_response(step_name: str, cli_name: str, stdout: str, stderr: str, exit_code: int, **extra) -> None:
    """Log response metadata plus previews for review debugging."""
    stdout_first, stdout_last = _preview_edges(stdout, _RESPONSE_PREVIEW_CHARS)
    stderr_first, stderr_last = _preview_edges(stderr, _RESPONSE_PREVIEW_CHARS)
    logger.debug(
        "ai_response_received",
        step=step_name,
        cli=cli_name,
        exit_code=exit_code,
        stdout_chars=len(stdout),
        stderr_chars=len(stderr),
        stdout_first_chars=stdout_first,
        stdout_last_chars=stdout_last,
        stderr_first_chars=stderr_first,
        stderr_last_chars=stderr_last,
        **extra,
    )
    if _ai_payload_logging_enabled():
        logger.debug(
            "ai_response_full",
            step=step_name,
            cli=cli_name,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            **extra,
        )


def _cli_failure_reason(response, cli_name: str) -> str:
    """Translate a failed headless CLI run into a reason the reviewer can act on.

    Raw stderr is usually noise, but the *kind* of failure decides what the user
    should do next, and that must reach the UI: an exhausted quota is waited out or
    routed to another CLI, a timeout is retried, a missing binary is installed. A
    bare "exit 1" leaves all three indistinguishable.
    """
    if response.quota_exhausted:
        return (
            f"'{cli_name}' has run out of usage quota — wait for it to reset or route "
            f"this task to another CLI in AI Configuration"
            + _cli_own_words(response)
        )
    if response.exit_code == 124:
        return f"'{cli_name}' timed out"
    if response.exit_code == 127:
        return f"'{cli_name}' is not installed"
    # The CLI's own message, when it fits on a line. A pattern list can only recognise
    # the failures it has seen, and the one it misses is the one worth reading: measured
    # 2026-09-22, "You've hit your session limit · resets 6:30pm" reached the user as
    # "exited with code 1" because the phrase was not in the list.
    return f"'{cli_name}' exited with code {response.exit_code}" + _cli_own_words(response)


_CLI_MESSAGE_MAX_CHARS = 200


def _cli_own_words(response) -> str:
    """The CLI's own one-line explanation, or nothing when it only produced noise."""
    for channel in (response.stderr, response.stdout):
        message = " ".join((channel or "").split())
        if message and len(message) <= _CLI_MESSAGE_MAX_CHARS:
            return f" — {message}"
    return ""


def _extract_referenced_commit_shas(reply_bodies: list[str]) -> list[str]:
    """Collect distinct SHA-like tokens mentioned in reply bodies."""
    seen: set[str] = set()
    shas: list[str] = []

    for body in reply_bodies:
        for match in _COMMIT_SHA_RE.findall(body or ""):
            sha = match.lower()
            if sha in seen:
                continue
            seen.add(sha)
            shas.append(sha)

    return shas


def _load_referenced_commit_contexts(
    ctx: WorkflowContext,
    threads: list[UICommentThread],
    pr: Optional[UIPullRequest] = None,
) -> dict[str, list[ReferencedCommitContext]]:
    """Fetch compact remote commit context for SHA references in the PR author's replies.

    Only replies authored by the PR author are scanned for SHAs, since the AI
    is deciding whether the author's response resolved the review comment; SHAs
    mentioned by other reviewers or bots aren't claims made by the author.

    For cross-repo (fork) PRs, referenced SHAs may only exist on the fork's
    head repository, so lookups are resolved against it instead of the base repo.
    """
    if not ctx.github:
        return {}

    repo_owner: Optional[str] = None
    repo_name: Optional[str] = None
    if pr and pr.is_cross_repository and pr.head_repository_owner and pr.head_repository_name:
        repo_owner = pr.head_repository_owner
        repo_name = pr.head_repository_name

    pr_author = pr.author_name if pr else None

    commit_cache: dict[str, ReferencedCommitContext | None] = {}
    contexts_by_thread: dict[str, list[ReferencedCommitContext]] = {}

    for thread in threads:
        reply_bodies = [
            reply.body for reply in thread.replies
            if pr_author is None or reply.author_login == pr_author
        ]
        referenced_shas = _extract_referenced_commit_shas(reply_bodies)
        if not referenced_shas:
            continue

        referenced_contexts: list[ReferencedCommitContext] = []
        for sha in referenced_shas[:_MAX_REFERENCED_COMMITS_PER_THREAD]:
            if sha not in commit_cache:
                result = ctx.github.get_commit_review_context(
                    sha,
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    max_files=_MAX_REFERENCED_COMMIT_FILES,
                    max_patch_chars=_MAX_REFERENCED_COMMIT_PATCH_CHARS,
                )
                match result:
                    case ClientSuccess(data=commit_context):
                        commit_cache[sha] = commit_context
                    case ClientError(error_message=err):
                        logger.debug(
                            "referenced_commit_context_unavailable",
                            thread_id=thread.thread_id,
                            sha=sha,
                            error=err,
                        )
                        commit_cache[sha] = None

            commit_context = commit_cache.get(sha)
            if commit_context is not None:
                referenced_contexts.append(commit_context)

        if referenced_contexts:
            contexts_by_thread[thread.thread_id] = referenced_contexts

    return contexts_by_thread


def _filter_invalid_inline_comments(ctx: WorkflowContext, pr_number: int, payload: dict) -> tuple[dict, list[dict]]:
    """Probe inline comments individually, keep only those GitHub accepts.

    Rejected comments are not dropped: their content moves into the review body
    (same format as the pre-submit general-body fallback), so a reviewer-approved
    finding is always published even when GitHub refuses its inline anchor.
    """
    if not ctx.github or not payload.get("comments"):
        return payload, []

    valid_comments: list[dict] = []
    rejected_comments: list[dict] = []

    for comment in payload.get("comments", []):
        probe_payload = {
            "commit_id": payload["commit_id"],
            "comments": [comment],
        }
        probe_result = ctx.github.create_draft_review(pr_number, probe_payload)
        match probe_result:
            case ClientSuccess(data=probe_review_id):
                valid_comments.append(comment)
                delete_result = ctx.github.delete_review(pr_number, probe_review_id)
                match delete_result:
                    case ClientError(error_message=err):
                        logger.warning(
                            "probe_review_delete_failed",
                            pr_number=pr_number,
                            review_id=probe_review_id,
                            error=err,
                        )
            case ClientError(error_message=err):
                rejection_kind = classify_github_review_rejection(err)
                rejected = {**comment, "error": err}
                rejected_comments.append(rejected)
                logger.warning(
                    "inline_comment_rejected_by_github",
                    pr_number=pr_number,
                    path=comment.get("path"),
                    line=comment.get("line"),
                    github_rejection_kind=rejection_kind,
                    error=err,
                )

    filtered_payload = {
        "commit_id": payload["commit_id"],
        "comments": valid_comments,
    }
    body_parts: list[str] = []
    if payload.get("body"):
        body_parts.append(payload["body"])
    for comment in rejected_comments:
        location = f"**{comment.get('path')}**" if comment.get("path") else "General"
        if comment.get("line"):
            location += f" (line {comment.get('line')})"
        body_parts.append(f"{location}:\n{comment.get('body', '')}")
    if body_parts:
        filtered_payload["body"] = "\n\n---\n\n".join(body_parts)
    return filtered_payload, rejected_comments


def _collapse_derived_findings(findings: list) -> tuple[list, int]:
    """Drop call-site findings that are derived from a stronger central finding."""
    central_findings = [finding for finding in findings if _is_central_path(finding.path)]
    if not central_findings:
        return findings, 0

    kept: list = []
    removed = 0
    for finding in findings:
        if _is_central_path(finding.path):
            kept.append(finding)
            continue

        if any(_is_derived_from_central(finding, central) for central in central_findings):
            removed += 1
            logger.debug(
                "finding_collapsed_to_root_cause",
                path=finding.path,
                title=finding.title,
            )
            continue

        kept.append(finding)
    return kept, removed


def _is_central_path(path: str) -> bool:
    return any(hint in path for hint in _CENTRAL_PATH_HINTS)


def _is_derived_from_central(finding, central) -> bool:
    if finding.path == central.path:
        return False
    if finding.category != central.category:
        return False

    finding_text = " ".join(filter(None, [finding.title, finding.why, finding.evidence, finding.suggested_comment])).lower()
    central_text = " ".join(filter(None, [central.title, central.why, central.evidence, central.suggested_comment])).lower()

    central_stem = central.path.split("/")[-1].replace(".kt", "").replace(".py", "").lower()
    shared_api = any(
        token in finding_text and token in central_text
        for token in ("launchcustomtab", "openurlordialog", "checkinternalorexternaluri", "ishostallowed", "onopenfailed", "onopensuccess")
    )
    # Only the FINDING mentioning the central file counts as a derivation signal —
    # the central finding mentions its own file stem practically by definition, so
    # checking central_text here would make this clause always true and reduce the
    # whole collapse condition to a 0.32 title similarity.
    mentions_central = central_stem in finding_text
    title_similarity = SequenceMatcher(None, finding.title.lower(), central.title.lower()).ratio()

    return (shared_api or mentions_central) and title_similarity >= 0.32


# ============================================================================
# UI HELPERS
# ============================================================================


def _show_review_action_and_get_decision(
    ctx: WorkflowContext,
    action: ReviewActionProposal,
    diff_hunk: str,
    idx: int,
    total: int,
    review_threads: Optional[List[UICommentThread]] = None,
    file_excerpt: Optional[str] = None,
) -> str:
    """
    Display a ReviewActionProposal and return the user's chosen decision.

    For resolve_thread actions, shows thread context and resolve confirmation.
    For reply_to_thread actions, shows the original thread context and proposed reply.
    For new_comment actions, shows just the proposed comment.

    ``file_excerpt`` carries real file content for findings the diff cannot anchor, so
    they are shown with their code rather than as an unsupported claim.

    Returns:
        "approve", "edit", "skip", or "exit"
    """
    ctx.textual.text("")

    # Handle resolve_thread actions differently
    if action.action_type == ReviewActionType.RESOLVE_THREAD:
        ctx.textual.bold_text(f"Thread {idx + 1} of {total}")
        ctx.textual.text("")

        # Show the original thread to be resolved
        if review_threads:
            from titan_plugin_github.widgets import CommentThread

            original_thread = next(
                (t for t in review_threads if t.thread_id == action.thread_id),
                None
            )
            if original_thread:
                ctx.textual.text("📌 Thread to resolve:")
                ctx.textual.mount(
                    CommentThread(
                        thread=original_thread,
                        options=[],  # No buttons in this display
                    )
                )
                ctx.textual.text("")

        ctx.textual.text("✓ Mark this thread as resolved")
        ctx.textual.text("")

        options = [
            ChoiceOption(value="approve", label="✓ Resolve", variant="success"),
            ChoiceOption(value="skip", label="— Skip", variant="default"),
        ]
        if idx < total - 1:
            options.append(ChoiceOption(value="exit", label="✗ Exit review", variant="error"))

        question = "What would you like to do with this thread?"
    else:
        # For reply_to_thread and new_comment actions
        ctx.textual.bold_text(f"Comment {idx + 1} of {total}")
        ctx.textual.text("")

        # For reply_to_thread actions, show the original thread context
        if action.action_type == ReviewActionType.REPLY_TO_THREAD and review_threads:
            from titan_plugin_github.widgets import CommentThread

            # Find the original thread
            original_thread = next(
                (t for t in review_threads if t.thread_id == action.thread_id),
                None
            )
            if original_thread:
                ctx.textual.text("📌 Original comment:")
                ctx.textual.mount(
                    CommentThread(
                        thread=original_thread,
                        options=[],  # No buttons in this display
                    )
                )
                ctx.textual.text("")
                ctx.textual.text("📝 Your reply:")

        # Show the action (proposed reply or new comment)
        from titan_plugin_github.widgets import CommentView
        ctx.textual.mount(
            CommentView.from_action(action, diff_hunk=diff_hunk, file_excerpt=file_excerpt)
        )
        ctx.textual.text("")

        options = [
            ChoiceOption(value="approve", label="✓ Approve", variant="success"),
            ChoiceOption(value="edit", label="✎ Edit", variant="default"),
            ChoiceOption(value="skip", label="— Skip", variant="default"),
        ]
        if idx < total - 1:
            options.append(ChoiceOption(value="exit", label="✗ Exit review", variant="error"))

        question = "What would you like to do with this comment?"

    result_container: dict = {}
    result_event = threading.Event()

    def on_choice(value):
        result_container["choice"] = value
        result_event.set()

    prompt = PromptChoice(
        question=question,
        options=options,
        on_select=on_choice,
    )
    ctx.textual.mount(prompt)
    result_event.wait()

    choice = result_container.get("choice", "skip")

    action_labels = {
        "approve": "✓ Resolved" if action.action_type == ReviewActionType.RESOLVE_THREAD else "✓ Approved",
        "edit": "✎ Edited",
        "skip": "— Skipped",
        "exit": "✗ Exit review",
    }
    action_variants = {
        "approve": "success",
        "edit": "default",
        "skip": "default",
        "exit": "warning",
    }

    def _replace_with_badge():
        from titan_cli.ui.tui.widgets.decision_badge import DecisionBadge
        try:
            prompt.remove()
        except Exception:
            pass
        try:
            target = ctx.textual._active_step_container or ctx.textual.output_widget
            target.mount(
                DecisionBadge(
                    action_labels.get(choice, choice),
                    variant=action_variants.get(choice, "default"),
                )
            )
        except Exception:
            pass

    ctx.textual.app.call_from_thread(_replace_with_badge)
    return choice


# ============================================================================
# STEP FUNCTIONS
# ============================================================================


def select_pr_for_code_review(ctx: WorkflowContext) -> WorkflowResult:
    """
    List all open PRs and ask user to select one.

    Assigned PRs (pending your review) appear first marked with ⭐.

    Outputs (saved to ctx.data):
        review_pr_number (int): Selected PR number
        review_pr_title (str): PR title
        review_pr_head (str): Head branch
        review_pr_base (str): Base branch

    Returns:
        Success: A PR was selected.
        Exit: No PRs, or the user cancelled.
        Error: If listing PRs fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Select PR to Review")

    if not ctx.github:
        ctx.textual.error_text("GitHub client not available")
        ctx.textual.end_step("error")
        return Error("GitHub client not available")

    with ctx.textual.loading("Fetching open PRs..."):
        all_result = ctx.github.list_all_prs()
        assigned_result = ctx.github.list_pending_review_prs()

    match all_result:
        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to fetch PRs: {err}")
            ctx.textual.end_step("error")
            return Error(f"Failed to fetch PRs: {err}")
        case ClientSuccess(data=all_prs_list):
            pass

    if not all_prs_list:
        ctx.textual.dim_text("No open PRs found in this repository.")
        ctx.textual.end_step("skip")
        return Exit("No open PRs found")

    # Build set of assigned PR numbers (ignore errors — best effort)
    assigned_numbers: set = set()
    match assigned_result:
        case ClientSuccess(data=assigned_prs):
            assigned_numbers = {pr.number for pr in assigned_prs}
        case ClientError():
            pass

    # Sort: assigned first, then the rest (preserving original order within each group)
    sorted_prs = [pr for pr in all_prs_list if pr.number in assigned_numbers] + \
                 [pr for pr in all_prs_list if pr.number not in assigned_numbers]

    options = [
        OptionItem(
            value=pr.number,
            title=build_pr_selection_title(
                pr,
                highlight_assigned=pr.number in assigned_numbers,
                include_review_badge=True,
            ),
            description=build_pr_selection_description(
                pr,
                include_author=True,
                include_checks=True,
            ),
        )
        for pr in sorted_prs
    ]

    assigned_count = len(assigned_numbers)
    question = f"Select a PR to review ({len(all_prs_list)} total{f', {assigned_count} assigned to you ⭐' if assigned_count else ''}):"

    try:
        selected = ctx.textual.ask_option(question, options)
    except Exception as e:
        ctx.textual.error_text(str(e))
        ctx.textual.end_step("error")
        return Error(str(e))

    if not selected:
        ctx.textual.warning_text("No PR selected")
        ctx.textual.end_step("skip")
        return Exit("User cancelled PR selection")

    selected_pr = next((pr for pr in sorted_prs if pr.number == selected), None)
    if not selected_pr:
        ctx.textual.error_text(f"PR #{selected} not found in list")
        ctx.textual.end_step("error")
        return Error(f"PR #{selected} not found in list")

    ctx.textual.success_text(f"Selected PR #{selected_pr.number}: {selected_pr.title}")
    ctx.textual.end_step("success")

    return Success(
        f"Selected PR #{selected_pr.number}",
        metadata={
            "review_pr_number": selected_pr.number,
            "review_pr_title": selected_pr.title,
            "review_pr_head": selected_pr.head_ref,
            "review_pr_base": selected_pr.base_ref,
        },
    )


def fetch_pr_review_bundle(ctx: WorkflowContext) -> WorkflowResult:
    """
    Fetch all data needed for a full PR review cycle.

    Builds a complete review bundle: PR metadata, diff, file stats,
    inline review threads (separate from general comments), and commit SHA.

    Inputs (from ctx.data):
        review_pr_number (int): PR number

    Outputs (saved to ctx.data):
        review_pr (UIPullRequest): Pull request details
        review_diff (str): Full unified diff
        review_changed_files (List[str]): Changed file paths (may be subset for large PRs)
        review_changed_files_with_stats (List[UIFileChange]): All files with add/del stats
        review_commit_sha (str): Head commit SHA
        review_threads (List[UICommentThread]): Inline review threads (unresolved)
        review_general_comments (List[UICommentThread]): General PR-level comments
        pr_template (str | None): PR template content if available

    Returns:
        Success: The step completed.
        Skip: Nothing to do (empty diff).
        Error: The step failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Fetch PR Review Bundle")

    pr_number = ctx.get("review_pr_number")
    if not pr_number:
        ctx.textual.error_text("No PR number in context (run select_pr_for_code_review first)")
        ctx.textual.end_step("error")
        return Error("No PR number in context (run select_pr_for_code_review first)")

    if not ctx.github:
        ctx.textual.error_text("GitHub client not available")
        ctx.textual.end_step("error")
        return Error("GitHub client not available")

    # Fetch PR details, files with stats, and commit SHA
    with ctx.textual.loading(f"Fetching PR #{pr_number} data..."):
        pr_result = ctx.github.get_pull_request(pr_number)
        files_result = ctx.github.get_pr_files_with_stats(pr_number)
        sha_result = ctx.github.get_pr_commit_sha(pr_number)

    # Validate PR
    match pr_result:
        case ClientSuccess(data=pr):
            pass
        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to fetch PR: {err}")
            ctx.textual.end_step("error")
            return Error(f"Failed to fetch PR: {err}")

    # Validate files
    match files_result:
        case ClientSuccess(data=all_files_with_stats):
            changed_file_paths = [f.path for f in all_files_with_stats]
        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to fetch changed files: {err}")
            ctx.textual.end_step("error")
            return Error(f"Failed to fetch files: {err}")

    # Fetch diff. For fork PRs, gh pr diff is the source of truth because the
    # head branch usually does not exist under the local origin remote.
    with ctx.textual.loading(f"Fetching PR #{pr_number} diff..."):
        diff_result, diff_is_github_source = _get_review_diff(ctx, pr_number, pr, all_files_with_stats)

    # Validate diff — fallback to per-file patches if PR is too large
    match diff_result:
        case ClientSuccess(data=diff):
            if not diff or not diff.strip():
                if all_files_with_stats:
                    ctx.textual.warning_text(
                        "Diff came back empty despite changed files in the PR."
                    )
                    ctx.textual.end_step("error")
                    return Error("Could not resolve PR diff despite changed files")
                ctx.textual.dim_text("PR diff is empty — nothing to review.")
                ctx.textual.end_step("success")
                return Exit("Empty PR diff")
        case ClientError(error_message=err) if "too_large" in err or "too large" in err.lower():
            ctx.textual.warning_text("PR diff is too large. Selecting files that matter...")

            # AI selects which files to review from the already-fetched stats
            if ctx.ai:
                with ctx.textual.loading(f"AI selecting from {len(all_files_with_stats)} files..."):
                    selected_paths = select_files_for_review(all_files_with_stats, ctx.ai)
            else:
                from ..operations.code_review_operations import MAX_FILES_FOR_REVIEW
                selected_paths = [f.path for f in all_files_with_stats[:MAX_FILES_FOR_REVIEW]]

            ctx.textual.dim_text(f"Reviewing {len(selected_paths)} of {len(all_files_with_stats)} files")
            changed_file_paths = selected_paths

            with ctx.textual.loading("Fetching patches for selected files..."):
                patches_result = ctx.github.get_pr_file_patches(pr_number, selected_paths)

            match patches_result:
                case ClientSuccess(data=patches_diff) if patches_diff:
                    diff = patches_diff
                    # Files-API patches ARE GitHub's diff hunks — valid as the
                    # publishable-lines source.
                    diff_is_github_source = True
                case ClientError(error_message=err):
                    ctx.textual.error_text(f"Failed to fetch file patches: {err}")
                    ctx.textual.end_step("error")
                    return Error(f"Could not fetch file patches: {err}")
                case _:
                    ctx.textual.end_step("error")
                    return Error("Could not fetch file patches for large PR")
        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to fetch diff: {err}")
            ctx.textual.end_step("error")
            return Error(f"Failed to fetch diff: {err}")

    # Validate commit SHA
    match sha_result:
        case ClientSuccess(data=commit_sha):
            pass
        case ClientError(error_message=err):
            ctx.textual.warning_text(f"Could not get commit SHA: {err}")
            commit_sha = ""

    # Display file changes summary
    formatted_files, formatted_summary = compute_diff_stat(diff)
    diff_manager = get_or_create_diff_manager(diff, ctx.data)

    # Attach GitHub's own diff as the publishable-lines source (D-008). The review diff
    # may be a local `git diff -U20` whose extra context lines GitHub rejects for inline
    # comments; publish validation must use GitHub's hunks. When unavailable, the manager
    # falls back to added-lines-only, which GitHub always accepts.
    github_diff = diff if diff_is_github_source else None
    publish_validation_source = "github_diff"
    if github_diff is None:
        github_diff_result = ctx.github.get_pr_diff(pr_number)
        match github_diff_result:
            case ClientSuccess(data=gh_diff) if gh_diff and gh_diff.strip():
                github_diff = gh_diff
            case _:
                # GitHub refuses to serve diffs over 20k lines (HTTP 406). A local
                # three-dot diff at 3 context lines produces near-identical hunks —
                # GitHub renders PR diffs from the merge base with -U3 context — so
                # it stands in as the publishable-lines source. Residual divergence
                # (rename detection edge cases) is absorbed by the 422 recovery.
                if ctx.git and not pr.is_cross_repository:
                    local_u3_result = ctx.git.get_branch_diff(
                        pr.base_ref, pr.head_ref, context_lines=3, use_remote=True
                    )
                    match local_u3_result:
                        case ClientSuccess(data=local_diff) if local_diff and local_diff.strip():
                            github_diff = local_diff
                            publish_validation_source = "local_u3_diff"
                        case _:
                            pass
                if github_diff is None:
                    publish_validation_source = "added_lines_only"
                    logger.warning(
                        "github_diff_unavailable_for_publish_validation",
                        pr_number=pr_number,
                        fallback="added_lines_only",
                    )
    if github_diff:
        diff_manager.attach_github_diff(github_diff)
    logger.debug(
        "publish_validation_diff_source",
        pr_number=pr_number,
        source=publish_validation_source,
    )

    ctx.textual.show_diff_stat(formatted_files, formatted_summary, title="Files affected:")

    # Fetch inline review threads and general comments separately
    review_threads = []
    general_comments = []
    review_current_user = None
    with ctx.textual.loading("Fetching existing review comments..."):
        threads_result = ctx.github.get_pr_review_threads(pr_number, include_resolved=True)
        match threads_result:
            case ClientSuccess(data=threads):
                review_threads = threads
            case ClientError(error_message=err):
                # Threads drive dedup against existing comments — reviewing without
                # them risks re-proposing duplicates, so the degradation must be visible.
                ctx.textual.warning_text(f"Could not fetch review threads: {err}")

        general_result = ctx.github.get_pr_general_comments(pr_number)
        match general_result:
            case ClientSuccess(data=general):
                general_comments = general
            case ClientError(error_message=err):
                ctx.textual.warning_text(f"Could not fetch general comments: {err}")

        current_user_result = ctx.github.get_current_user()
        match current_user_result:
            case ClientSuccess(data=current_user):
                review_current_user = current_user
            case ClientError(error_message=err):
                ctx.textual.warning_text(f"Could not get current user: {err}")

    ctx.textual.dim_text(
        f"{len(changed_file_paths)} files · {formatted_summary} · "
        f"{len(review_threads)} review thread(s) · {len(general_comments)} general comment(s)"
    )

    ctx.textual.end_step("success")

    pr_template = ctx.github.get_pr_template()

    return Success(
        f"Fetched PR #{pr_number} review bundle",
        metadata={
            "review_pr": pr,
            "review_diff": diff,
            "review_diff_manager": diff_manager,
            "review_changed_files": changed_file_paths,
            "review_changed_files_with_stats": all_files_with_stats,
            "review_commit_sha": commit_sha,
            "review_threads": review_threads,
            "review_general_comments": general_comments,
            "review_current_user": review_current_user,
            "pr_template": pr_template,
        },
    )


def _get_review_diff(
    ctx: WorkflowContext,
    pr_number: int,
    pr: UIPullRequest,
    all_files_with_stats: list,
):
    """
    Resolve the most trustworthy diff source for a PR review.

    Returns:
        Tuple of (diff ClientResult, is_github_source). ``is_github_source`` is True when
        the diff came from GitHub itself (``gh pr diff``) — that diff can then double as
        the publishable-lines source without a second fetch.
    """
    if pr.is_cross_repository:
        logger.info(
            "review_diff_using_github",
            pr_number=pr_number,
            reason="cross_repository_pr",
            head_repository_owner=pr.head_repository_owner,
        )
        return ctx.github.get_pr_diff(pr_number), True

    if not ctx.git:
        logger.debug("diff_source_selected", source="gh_pr_diff", reason="git_plugin_unavailable")
        return ctx.github.get_pr_diff(pr_number), True

    fetch_result = ctx.git.fetch(all=True)
    match fetch_result:
        case ClientError(error_message=err):
            logger.warning("git_fetch_failed", error=err, action="continuing_with_diff")
        case _:
            pass

    git_diff_result = ctx.git.get_branch_diff(
        pr.base_ref,
        pr.head_ref,
        context_lines=20,
        use_remote=True,
    )

    match git_diff_result:
        case ClientSuccess(data=diff) if diff and diff.strip():
            return git_diff_result, False
        case ClientSuccess(data=_):
            if all_files_with_stats:
                logger.warning(
                    "git_diff_empty_with_changed_files",
                    pr_number=pr_number,
                    base_ref=pr.base_ref,
                    head_ref=pr.head_ref,
                    files_changed=len(all_files_with_stats),
                )
                return ctx.github.get_pr_diff(pr_number), True
            return git_diff_result, False
        case ClientError(error_message=err):
            logger.warning(
                "git_diff_failed_falling_back_to_github",
                pr_number=pr_number,
                base_ref=pr.base_ref,
                head_ref=pr.head_ref,
                error=err,
            )
            return ctx.github.get_pr_diff(pr_number), True


REVIEW_AI_CALLS_KEY = "review_ai_calls"


class _PinnedModelCli:
    """A headless adapter that pins the user's model and records what each call cost.

    These steps drive the adapter directly rather than through `generate_text`, so the
    model the user chose in AI Configuration would otherwise never reach the CLI - it
    is injected by the executor, on a path this file does not take. Wrapping the
    adapter once, where it is resolved, applies the setting to every call, including
    the ones a future step adds: forgetting `model=` at a call site is no longer
    possible, because no call site passes it.

    An explicit `model=` from a caller still wins, matching the executor's own rule.

    The same argument applies to cost telemetry, which is why it lives here too rather
    than at the five `adapter.execute(...)` call sites: a phase added later is measured
    without anyone remembering to measure it. Records go on `ctx.data` (never on step
    metadata, which is scanned for secrets) and appending to a list is safe from the
    findings phase's worker threads.
    """

    def __init__(self, adapter, model: Optional[str], ctx=None, phase: Optional[str] = None):
        self._adapter = adapter
        self._model = model
        self._ctx = ctx
        self._phase = phase or "unknown"

    @property
    def pinned_model(self) -> Optional[str]:
        """The model this wrapper injects, for the announcement to name it."""
        return self._model

    def __getattr__(self, name):
        """Everything else - cli_name, the supports_* capabilities - is the adapter's."""
        return getattr(self._adapter, name)

    def execute(self, prompt, **kwargs):
        # `is None`, not setdefault: the executor's rule is that a call-site model counts
        # only when it is not None, so a caller forwarding an optional model=None must
        # mean "no opinion" here too, rather than suppressing the user's pin entirely.
        if kwargs.get("model") is None:
            kwargs["model"] = self._model
        started_at = time.monotonic()
        try:
            response = self._adapter.execute(prompt, **kwargs)
        except BaseException:
            # A cancelled or crashed call consumed real tokens the CLI never got to
            # report. Recording a priced zero here would be a lie, so nothing is
            # recorded and the raise stands - WorkflowAborted must not be swallowed.
            raise
        self._record(prompt, kwargs, response, time.monotonic() - started_at)
        return response

    def _record(self, prompt, kwargs, response, duration_seconds: float) -> None:
        """Append one call record and log it. Never allowed to break the review."""
        try:
            usage = getattr(response, "usage", None)
            record = AICallRecord(
                phase=self._phase,
                cli=self._adapter.cli_name.value,
                prompt_chars=len(prompt or ""),
                duration_seconds=round(duration_seconds, 3),
                succeeded=bool(getattr(response, "succeeded", False)),
                model_requested=kwargs.get("model"),
                model_reported=getattr(usage, "model_reported", None),
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                cache_read_tokens=getattr(usage, "cache_read_tokens", None),
                cache_write_tokens=getattr(usage, "cache_write_tokens", None),
                reasoning_tokens=getattr(usage, "reasoning_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
                cost_usd=getattr(usage, "cost_usd", None),
                usage_source=getattr(usage, "source", None),
            )
            logger.debug(
                "ai_call_cost",
                phase=record.phase,
                cli=record.cli,
                model_requested=record.model_requested,
                model_reported=record.model_reported,
                model_substituted=record.model_substituted,
                effort=kwargs.get("effort"),
                prompt_chars=record.prompt_chars,
                duration_seconds=record.duration_seconds,
                succeeded=record.succeeded,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                # Anthropic counts cached input OUTSIDE input_tokens, so on claude a
                # 90k-char prompt reads input_tokens=107: the prompt is in these two.
                cache_read_tokens=record.cache_read_tokens,
                cache_write_tokens=record.cache_write_tokens,
                reasoning_tokens=record.reasoning_tokens,
                total_tokens=record.total_tokens,
                # Absent rather than zero when the CLI reports no price: codex and agy
                # never do, and gemini reports nothing at all.
                cost_usd=record.cost_usd,
                # Present only when the session used more than one model (subagents).
                model_costs=getattr(usage, "model_costs", None),
                usage_source=record.usage_source,
            )
            if self._ctx is not None:
                self._ctx.data.setdefault(REVIEW_AI_CALLS_KEY, []).append(record)
        except Exception as exc:  # pragma: no cover - telemetry must never break a review
            logger.debug("ai_call_cost_record_failed", phase=self._phase, error=str(exc))



def log_review_ai_cost(ctx, scope: str) -> None:
    """Emit the running cost summary for this review, at DEBUG.

    DEBUG on purpose: the file handler runs at DEBUG in development and INFO in
    production, so this is a development instrument by construction and never grows an
    end user's log. Called at more than one point because a review can end at an
    interactive gate without reaching its last step - `scope` says which point spoke.
    """
    records = (ctx.data or {}).get(REVIEW_AI_CALLS_KEY) or []
    if not records:
        return
    summary = summarize_ai_calls(list(records))
    logger.debug(
        "review_ai_cost_summary",
        scope=scope,
        calls=summary.calls,
        failed_calls=summary.failed_calls,
        duration_seconds=summary.duration_seconds,
        prompt_chars=summary.prompt_chars,
        total_tokens=summary.total_tokens,
        cost_usd=summary.cost_usd,
        cost_is_complete=summary.cost_is_complete,
        cost_per_call_usd=summary.cost_per_call_usd,
        calls_missing_cost=summary.calls_missing_cost,
        calls_missing_tokens=summary.calls_missing_tokens,
        substituted_model_calls=summary.substituted_model_calls,
        clis=summary.clis,
        models_reported=summary.models_reported,
        phases=[
            {
                "phase": p.phase,
                "calls": p.calls,
                "failed_calls": p.failed_calls,
                "duration_seconds": p.duration_seconds,
                "prompt_chars": p.prompt_chars,
                "total_tokens": p.total_tokens,
                "cost_usd": p.cost_usd,
                "calls_missing_cost": p.calls_missing_cost,
            }
            for p in summary.phases
        ],
        summary=format_cost_summary(summary),
    )


def _resolve_headless_adapter(cli_preference: str):
    """Return the first available headless adapter, or None."""
    if cli_preference == "auto":
        available = list_available_headless_clis()
        return get_headless_adapter(available[0]) if available else None

    try:
        candidate = get_headless_adapter(cli_preference)
    except ValueError:
        return None

    return candidate if candidate.is_available() else None


def _resolve_review_adapter(
    ctx: WorkflowContext, step: Callable
) -> Tuple[Optional[object], Optional[str], bool]:
    """
    Return the headless CLI configured for this step's task, or None plus the reason.

    The user's per-task choice (AI Configuration screen) decides which CLI runs a
    review step, so no step asks. `None` comes back with a user-facing reason when
    the task is off, no default CLI is set, the configured one isn't installed, or
    the stored preference is something this step cannot run. Every caller shows that
    reason and then takes its own degraded path: a review without AI is a worse
    result, not a crash, and the reason is what lets the user fix it.

    The third element is True only when the user deliberately turned AI off for
    this task. Callers that must not present "AI never ran" as a clean result use
    it to tell the intentional skip apart from a routing failure.

    Without the façade (a step called outside a workflow run) the previous behavior
    stands: first available CLI.
    """
    router = getattr(ctx, "ai_router", None)
    if router is None:
        # No façade means no configuration to read either, so there is no pinned model
        # to honor - the bare adapter is the whole of what is known here.
        return _resolve_headless_adapter("auto"), None, False

    resolution = router.resolve(policy=step)

    if isinstance(resolution, AIRouteNeedsInput):
        return None, f"{resolution.reason} — set it in AI Configuration (main menu)", False

    if resolution.provider == AIProviderType.OFF:
        return None, "AI is turned off for this task", True

    if resolution.provider != AIProviderType.CLI_HEADLESS or not resolution.cli:
        return None, (
            f"'{resolution.provider}' cannot run this step, which needs a CLI "
            f"— change it in AI Configuration (main menu)"
        ), False

    adapter = _resolve_headless_adapter(resolution.cli)
    if adapter is None:
        return None, f"the configured CLI '{resolution.cli}' is not available", False

    model = router.model_for_decision(resolution)
    # Logged at the decision, not at each call: these steps drive the CLI themselves, so
    # nothing else in the log says which model they ran with - which is precisely what
    # made an earlier drop of this setting invisible until someone read the CLI's own
    # database.
    logger.info(
        "review_cli_resolved",
        step=getattr(step, "__name__", None),
        cli=resolution.cli,
        model=model,
    )
    return (
        _PinnedModelCli(adapter, model, ctx=ctx, phase=_step_phase(step)),
        None,
        False,
    )


def _step_phase(step) -> str:
    """The routing task this step declared, which is also its cost phase.

    Reusing the declared task rather than inventing a phase name keeps the cost
    log joinable to the routing log and to the model the user pinned for it.
    """
    policy = getattr(step, "ai_policy", None)
    task = getattr(policy, "task", None)
    return str(task) if task else str(getattr(step, "__name__", "unknown"))


def _route_failure_reason(route_note: Optional[str], ai_off: bool) -> str:
    """Why no AI ran, in words that distinguish a choice from a problem.

    `_resolve_review_adapter` returns `ai_off` precisely so a deliberate skip is not
    reported as a failure. Both of these steps were discarding it and calling everything
    "no CLI available", which sent a user looking for a misconfiguration they had made
    on purpose - or hid one they had not.
    """
    if ai_off:
        return "AI is off for this task"
    return route_note or "no CLI available"


def _announce_review_adapter(ctx: WorkflowContext, adapter: object) -> None:
    """Announce which CLI - and which model - will run this review step.

    These steps drive the adapter themselves, so they announce by hand rather than
    through the façade's `announce=`. The wording follows `route_summary()` so a review
    reads the same as every other AI step, and it names the MODEL because a task can now
    pin one: "claude" alone no longer answers "did my pin run?".
    """
    if not adapter or not hasattr(adapter, "cli_name"):
        return
    cli = adapter.cli_name.value
    model = getattr(adapter, "pinned_model", None)
    ctx.textual.ai_chip(
        f"{cli} / {model} · CLI, automatic" if model else f"{cli} · CLI, automatic"
    )


# ============================================================================
# PHASE 2: CHEAP CONTEXT STEPS (pre-AI, deterministic)
# ============================================================================


def _fetch_local_churn_for_truncated_files(
    ctx: WorkflowContext, pr: UIPullRequest, files: list
) -> Optional[dict]:
    """Fetch real per-file counters from local git when the API reports 0/0.

    GitHub's files endpoint returns additions=0/deletions=0 for files whose diff
    it cannot render (too large or binary). Left as-is, those files score as if
    nothing changed. A local numstat has the exact counters — available for
    same-repo PRs, where the fetch step already ran `git fetch --all`. Fork PRs
    and sessions without the git plugin keep the API values.
    """
    has_truncated = any(
        f.additions == 0 and f.deletions == 0 and f.status.value != "renamed" for f in files
    )
    if not has_truncated or not ctx.git or pr.is_cross_repository:
        return None

    numstat_result = ctx.git.get_branch_numstat(pr.base_ref, pr.head_ref, use_remote=True)
    match numstat_result:
        case ClientSuccess(data=churns):
            churn_by_path = {c.path: (c.additions, c.deletions) for c in churns if not c.is_binary}
            logger.debug(
                "manifest_churn_fallback",
                truncated_candidates=sum(
                    1 for f in files if f.additions == 0 and f.deletions == 0
                ),
                numstat_files=len(churn_by_path),
            )
            return churn_by_path
        case ClientError(error_message=err):
            logger.warning("manifest_numstat_failed", error=err)
            return None
    return None


def build_change_manifest(ctx: WorkflowContext) -> WorkflowResult:
    """
    Build a structured manifest of the PR changes (no AI involved).

    Converts UIFileChange objects into a typed ChangeManifest that serves
    as cheap context for both AI-directed workflows.

    Inputs (from ctx.data):
        review_pr (UIPullRequest): Pull request details
        review_changed_files_with_stats (List[UIFileChange]): Files with add/del stats

    Outputs (saved to ctx.data):
        change_manifest (ChangeManifest): Structured PR context

    Returns:
        Success: The step completed.
        Error: The step failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Build Change Manifest")

    pr = ctx.get("review_pr")
    files = ctx.get("review_changed_files_with_stats", [])

    if not pr:
        ctx.textual.error_text("No PR data in context (run fetch_pr_review_bundle first)")
        ctx.textual.end_step("error")
        return Error("No PR data in context (run fetch_pr_review_bundle first)")

    churn_by_path = _fetch_local_churn_for_truncated_files(ctx, pr, files)

    try:
        manifest = build_change_manifest_operation(
            pr, files, churn_by_path=churn_by_path
        )
    except Exception as e:
        ctx.textual.error_text(f"Failed to build change manifest: {e}")
        ctx.textual.end_step("error")
        return Error(f"Failed to build change manifest: {e}")

    test_count = sum(1 for f in manifest.files if f.is_test)
    docs_count = sum(1 for f in manifest.files if f.is_docs)
    config_count = sum(1 for f in manifest.files if f.is_config)
    generated_count = sum(1 for f in manifest.files if f.is_generated)
    lockfile_count = sum(1 for f in manifest.files if f.is_lockfile)
    static_resource_count = sum(1 for f in manifest.files if f.is_static_resource)
    rename_only_count = sum(1 for f in manifest.files if f.is_rename_only)
    ctx.textual.success_text(
        f"✓ {len(manifest.files)} files analysed"
        + (f" ({test_count} test files)" if test_count else "")
        + f" · +{manifest.total_additions} -{manifest.total_deletions}"
    )
    logger.info(
        "change_manifest_census",
        tests=test_count,
        docs=docs_count,
        config=config_count,
        generated=generated_count,
        lockfiles=lockfile_count,
        static_resources=static_resource_count,
        rename_only=rename_only_count,
    )
    ctx.textual.end_step("success")
    return Success("Change manifest built", metadata={"change_manifest": manifest})


def build_existing_comments_index(ctx: WorkflowContext) -> WorkflowResult:
    """
    Build a compact index of existing PR comments for deduplication.

    Flattens inline review threads and general PR comments into a lightweight
    list of ExistingCommentIndexEntry objects. The index is used later to
    avoid AI findings that duplicate comments already posted.

    Inputs (from ctx.data):
        review_threads (List[UICommentThread]): Inline review threads
        review_general_comments (List[UICommentThread]): General PR-level comments

    Outputs (saved to ctx.data):
        existing_comments_index (List[ExistingCommentIndexEntry])

    Returns:
        Success: The step completed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Build Existing Comments Index")

    threads = ctx.get("review_threads", [])
    general = ctx.get("review_general_comments", [])

    try:
        index = build_existing_comments_index_operation(threads, general)
    except Exception as e:
        ctx.textual.error_text(f"Failed to build comments index: {e}")
        ctx.textual.end_step("error")
        return Error(f"Failed to build comments index: {e}")

    resolved_count = sum(1 for e in index if e.is_resolved)
    adjudicated_count = sum(1 for e in index if e.is_adjudicated)
    msg = f"✓ {len(index)} existing comment(s) indexed"
    if resolved_count:
        msg += f" ({resolved_count} resolved)"
    ctx.textual.success_text(msg)
    logger.info(
        "existing_comments_index_built",
        existing_comments_total=len(index),
        resolved_comments_count=resolved_count,
        unresolved_comments_count=len(index) - resolved_count,
        adjudicated_threads_count=adjudicated_count,
    )
    ctx.textual.end_step("success")
    return Success("Comments index built", metadata={"existing_comments_index": index})


def _split_display_path(path: str, keep_dirs: int = 2) -> tuple[str, str]:
    """(file name, shortened directory) -- the name is what a reader scans for.

    The directory keeps its first segment (the module: `app`, `network`) and its last
    `keep_dirs`, which is where files differ; the shared middle (`src/main/kotlin/com/...`)
    becomes `…`.
    """
    parts = path.split("/")
    name, dirs = parts[-1], parts[:-1]
    if len(dirs) > keep_dirs + 1:
        dirs = [dirs[0], "…", *dirs[-keep_dirs:]]
    return name, "/".join(dirs)


def _display_file_label(path: str) -> str:
    """`Name.kt  app/…/dir` as markup: the name bold, where it lives dimmed."""
    from titan_cli.ui.tui.widgets.collapsible_list import escape_markup

    name, directory = _split_display_path(path)
    label = f"[bold]{escape_markup(name)}[/bold]"
    return f"{label}  [dim]{escape_markup(directory)}[/dim]" if directory else label


def _attach_content_provider(diff_manager, root: Optional[str]) -> None:
    """
    Give the diff manager a way to read whole files from ``root``.

    Only call this with a root already verified to hold the PR's head revision — the
    provider is trusted to return the code the diff describes.
    """
    if diff_manager is None or not root:
        return

    from ..operations.review_material_operations import read_file_content

    diff_manager.attach_content_provider(lambda path: read_file_content(path, root))


def _write_review_material(
    ctx: WorkflowContext,
    worktree_path: str,
    manifest,
    diff_manager,
    threads: list,
    general_comments: list,
) -> Optional[dict]:
    """Write the review's material into the worktree; map each changed path to whether its
    base version exists. None when it could not be written.

    The base is the merge base of the PR head and its base branch: the commit GitHub's diff
    is computed against, so the base versions are exactly the "before" of that diff.
    """
    from ..operations.review_material_operations import (
        PR_FILE,
        WHOLE_DIFF_FILE,
        base_file_path,
        diff_file_path,
        prepare_material_dir,
        diff_unavailable,
        render_file_diff,
        render_pr_file,
        safe_material_target,
    )

    pr = manifest.pr
    if not ctx.git or not pr or diff_manager is None:
        return None
    head_ref = review_head_ref(pr.number)
    base_ref = review_base_ref(pr.number)
    match ctx.git.fetch_refspec(ctx.git.default_remote, f"+refs/heads/{pr.base}:{base_ref}"):
        case ClientError(error_message=err):
            logger.warning("review_material_base_fetch_failed", base=pr.base, error=err)
            return None
        case _:
            pass
    match ctx.git.get_merge_base(head_ref, base_ref):
        case ClientSuccess(data=merge_base):
            pass
        case ClientError(error_message=err):
            logger.warning("review_material_merge_base_failed", error=err)
            return None

    root = Path(worktree_path)
    has_base: dict[str, bool] = {}
    whole_diff: list[str] = []
    no_diff = 0
    try:
        prepare_material_dir(root)
        for entry in manifest.files:
            hunks = diff_manager.get_hunk_texts(entry.path)
            unavailable = diff_unavailable(hunks, entry.additions, entry.deletions)
            if unavailable:
                no_diff += 1
            rendered = render_file_diff(entry.path, hunks, unavailable=unavailable)
            whole_diff.append(rendered)
            target = safe_material_target(root, diff_file_path(entry.path))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered)
            match ctx.git.get_file_at_ref(merge_base, entry.previous_path or entry.path):
                case ClientSuccess(data=str() as content):
                    base_target = safe_material_target(root, base_file_path(entry.path))
                    base_target.parent.mkdir(parents=True, exist_ok=True)
                    base_target.write_text(content)
                    has_base[entry.path] = True
                case _:
                    has_base[entry.path] = False
        safe_material_target(root, WHOLE_DIFF_FILE).write_text("\n".join(whole_diff))
        safe_material_target(root, PR_FILE).write_text(render_pr_file(pr, threads, general_comments, merge_base))
    except OSError as exc:
        logger.warning("review_material_not_written", error=str(exc))
        return None

    logger.info(
        "review_material_written",
        files=len(has_base),
        base_versions=sum(has_base.values()),
        diff_unavailable=no_diff,
        threads=len(threads),
        general_comments=len(general_comments),
        merge_base=merge_base,
    )
    return has_base


def write_review_material(ctx: WorkflowContext) -> WorkflowResult:
    """
    Put what the review would otherwise fetch into the PR worktree, as files.

    `.titan-review/pr.md` (description and every review comment), `pr.diff` (the whole
    diff), `diffs/<path>.diff` (each file's, lines labelled and numbered) and
    `base/<path>` (each changed file before the PR). The session opens them as it needs
    them; none of it goes in the prompt, which is re-read on every turn.

    A worktree is required: the review reads the PR's code there.

    Inputs (from ctx.data):
        change_manifest (ChangeManifest)
        review_diff_manager (DiffContextManager)
        review_threads, review_general_comments (List[UICommentThread])
        worktree_path (str)

    Outputs (saved to ctx.data):
        review_material (dict[str, bool]): each changed path -> whether it has a base version

    Returns:
        Success: The step completed.
        Error: The step failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    from ..operations.review_material_operations import diff_unavailable

    ctx.textual.begin_step("Write Review Material")

    manifest = ctx.get("change_manifest")
    worktree_path = ctx.data.get("worktree_path")
    if not manifest:
        ctx.textual.error_text("No change manifest in context")
        ctx.textual.end_step("error")
        return Error("No change manifest in context")
    if not worktree_path:
        message = (
            "No review worktree: the review reads the PR checked out in one. "
            "Check the Create Worktree step above."
        )
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
        return Error(message)

    diff_manager = ctx.get("review_diff_manager")
    # The same root powers the comment-rendering path, so a finding about pre-existing
    # code can show that code instead of nothing.
    _attach_content_provider(diff_manager, worktree_path)

    material = _write_review_material(
        ctx,
        worktree_path,
        manifest,
        diff_manager,
        ctx.get("review_threads", []) or [],
        ctx.get("review_general_comments", []) or [],
    )
    if material is None:
        message = "The review material could not be written into the worktree (see the log)."
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
        return Error(message)

    ctx.textual.success_text(
        f"✓ {len(material)} diffs, {sum(material.values())} base versions, "
        f"the PR and its comments in .titan-review/"
    )
    missing = sum(
        diff_unavailable(diff_manager.get_hunk_texts(e.path), e.additions, e.deletions)
        for e in manifest.files
    )
    if missing:
        ctx.textual.warning_text(
            f"{missing} file(s) have no diff available (marked 'read the file' for the session)"
        )
    ctx.textual.end_step("success")
    return Success("Review material written", metadata={"review_material": material})


def _repo_file_checker(project_root: Optional[str]):
    """A predicate for "this relative path is a real file in the reviewed tree", or None.

    Resolved and required to stay under the root, so a model's `../../etc/passwd`
    cannot be dressed up as a repository file.
    """
    if not project_root:
        return None
    root = Path(project_root).resolve()

    def _is_repo_file(relative: str) -> bool:
        if not relative or Path(relative).is_absolute():
            return False
        candidate = (root / relative).resolve()
        return candidate.is_relative_to(root) and candidate.is_file()

    return _is_repo_file


def _highlight_inline_code(text: str) -> str:
    """`code` spans from a model's prose -> bold, so identifiers stand out on screen."""
    return re.sub(r"`([^`\n]+)`", r"[bold]\1[/bold]", text)


def _review_tool_options(adapter) -> dict:
    """The tool, effort and spending options this adapter can enforce on the session."""
    from ..operations.findings_operations import (
        REVIEW_ALLOWED_TOOLS,
        REVIEW_DISALLOWED_TOOLS,
        REVIEW_EFFORT,
        REVIEW_MAX_BUDGET_USD,
    )

    restrict = adapter.supports_tool_restriction
    disallowed = list(REVIEW_DISALLOWED_TOOLS)
    if not adapter.supports_subagents:
        # The prompt does not offer subagents to this CLI, so the session must not spawn
        # them unverified either (grok turns this into --no-subagents).
        disallowed.append("Agent")
    return {
        "disallowed_tools": disallowed if restrict else None,
        "allowed_tools": list(REVIEW_ALLOWED_TOOLS) if restrict else None,
        "effort": REVIEW_EFFORT if adapter.supports_effort_control else None,
        "max_budget_usd": REVIEW_MAX_BUDGET_USD,
    }


def _retry_review_reformat(adapter, previous_stdout: str, cwd: Optional[str], structured: bool):
    """Ask the same CLI to reformat its own previous answer, without reviewing again."""
    from ..operations.findings_operations import free_review_json_schema, parse_findings_response

    reformat_prompt = build_json_reformat_prompt(previous_stdout, kind="array")
    _log_ai_prompt("ai_review_findings_reformat_retry", adapter.cli_name.value, reformat_prompt)
    response = run_interruptible(
        lambda: adapter.execute(
            reformat_prompt,
            cwd=cwd,
            timeout=REFORMAT_RETRY_TIMEOUT_SECONDS,
            json_schema=free_review_json_schema() if structured else None,
            **_review_tool_options(adapter),
        )
    )
    _log_ai_response(
        step_name="ai_review_findings_reformat_retry",
        cli_name=adapter.cli_name.value,
        stdout=response.stdout,
        stderr=response.stderr,
        exit_code=response.exit_code,
    )
    if not response.succeeded:
        return ClientError(
            error_message=f"Reformat retry failed: {_cli_failure_reason(response, adapter.cli_name.value)}",
            error_code="REFORMAT_RETRY_FAILED",
            log_level="warning",
        )
    return parse_findings_response(response.stdout, structured=structured)


def _render_rejected_paths(ctx: WorkflowContext, rejected: list[dict]) -> None:
    """Name every finding dropped because its file does not exist in the reviewed tree."""
    from titan_cli.ui.tui.widgets.collapsible_list import escape_markup

    ctx.textual.text(" ")
    ctx.textual.warning_text(f"Discarded {len(rejected)} finding(s) about files that do not exist:")
    for item in rejected:
        ctx.textual.text(f"  {_display_file_label(item.get('path', ''))}")
        if item.get("title"):
            ctx.textual.text(f"  ↳ {_highlight_inline_code(escape_markup(item['title']))}")


@declare_ai_usage(
    task=AITask.CODE_REVIEW_FINDINGS,
    executes=[AIProviderType.CLI_HEADLESS],
    enforces=True,
)
def ai_review_findings(ctx: WorkflowContext) -> WorkflowResult:
    """Run the review session, and report its cost even if it is abandoned.

    The wrapper exists for the `finally`: the session is where a review spends almost
    everything, and an interrupted run is exactly when the user wants to know what it
    cost. `WorkflowAborted` is a `BaseException`, so `finally` still runs on it.

    Inputs (from ctx.data):
        change_manifest (ChangeManifest)
        worktree_path (str): with the material `write_review_material` left in it

    Outputs (saved to ctx.data):
        raw_findings (list): the session's findings, mapped onto `Finding`'s fields
        ai_findings_failed (bool): True when no review happened

    Returns:
        Success: With the raw findings, or with none when AI is off for the task.
        Error: If the session could not run or produced nothing readable.
    """
    try:
        return _ai_review_findings(ctx)
    finally:
        log_review_ai_cost(ctx, scope="findings_phase")


def _fail_review(ctx: WorkflowContext, reason: str) -> WorkflowResult:
    """No review happened: say so, and publish empty findings for the steps after."""
    from ..operations.findings_operations import build_default_findings

    ctx.data["raw_findings"] = build_default_findings()
    ctx.data["ai_findings_failed"] = True
    logger.error("review_session_failed", reason=reason)
    ctx.textual.error_text(f"{reason} — no code was reviewed. Do not treat this as a clean review.")
    ctx.textual.end_step("error")
    return Error(f"Review failed: {reason}")


def _ai_review_findings(ctx: WorkflowContext) -> WorkflowResult:
    """
    The review: one free-form session of the configured CLI in the PR worktree.

    The CLI reviews the PR as it would if a user asked it to -- its own tools, subagents
    for a large PR, read-only git -- with the material `write_review_material` left in
    the worktree. Titan prescribes no procedure; it asks only for the answer's shape, and
    everything after (dedupe, anchoring, approval, publishing) is Titan's.

    Which CLI runs it comes from the `code_review_findings` task preference
    (AI Configuration screen), not from the workflow.

    Inputs (from ctx.data):
        change_manifest (ChangeManifest)
        worktree_path (str)

    Outputs (saved to ctx.data):
        raw_findings (list): the session's findings, mapped onto `Finding`'s fields
        ai_findings_failed (bool)

    Returns:
        Success: The step completed.
        Error: The step failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Review")
    # Failed until the session's answer is in: an exception anywhere below must not leave
    # the publishing step presenting an unreviewed PR as clean.
    ctx.data["ai_findings_failed"] = True

    from ..operations.findings_operations import (
        REVIEW_TIMEOUT_SECONDS,
        build_default_findings,
        build_free_review_prompt,
        free_review_json_schema,
        parse_findings_response,
        partition_findings_by_path,
        to_finding_payload,
    )

    manifest = ctx.get("change_manifest")
    worktree_path = ctx.data.get("worktree_path")
    if not manifest or not manifest.pr or not worktree_path:
        return _fail_review(ctx, "No change manifest or review worktree in context")

    adapter, route_note, ai_off = _resolve_review_adapter(ctx, ai_review_findings)
    if not adapter:
        reason = route_note or "No headless CLI available"
        if ai_off:
            # The user turned AI off for this task: nothing failed, nothing was meant to run.
            ctx.textual.warning_text(f"{reason} — skipping the review")
            ctx.textual.end_step("success")
            return Success(
                "No findings (AI is off for this task)",
                metadata={"raw_findings": build_default_findings(), "ai_findings_failed": False},
            )
        return _fail_review(ctx, f"{reason} — the review could not run")

    _announce_review_adapter(ctx, adapter)

    # A schema makes the CLI return its findings through a validated tool call instead of
    # trusting a "respond only with JSON" instruction a model may ignore after a long session.
    structured = adapter.supports_structured_output
    options = _review_tool_options(adapter)
    pr = manifest.pr
    prompt = build_free_review_prompt(
        pr.number,
        pr.title,
        pr.head,
        pr.base,
        worktree_path,
        use_subagents=adapter.supports_subagents,
    )
    cli = adapter.cli_name.value
    _log_ai_prompt("ai_review_findings", cli, prompt, files=len(manifest.files))

    started_at = time.monotonic()
    with ctx.textual.loading(f"{cli.capitalize()} is reviewing the PR…"):
        response = run_interruptible(
            lambda: adapter.execute(
                prompt,
                cwd=worktree_path,
                timeout=REVIEW_TIMEOUT_SECONDS,
                json_schema=free_review_json_schema() if structured else None,
                **options,
            )
        )
    logger.info(
        "review_session",
        cli=cli,
        files=len(manifest.files),
        duration_seconds=round(time.monotonic() - started_at, 3),
        timeout_seconds=REVIEW_TIMEOUT_SECONDS,
        exit_code=response.exit_code,
        timed_out=response.exit_code == 124,
        structured_output=structured,
        **{key: value for key, value in options.items() if value is not None},
    )
    _log_ai_response(
        step_name="ai_review_findings",
        cli_name=cli,
        stdout=response.stdout,
        stderr=response.stderr,
        exit_code=response.exit_code,
    )
    _log_session_activity(cli, response.activity)
    if not response.succeeded:
        return _fail_review(ctx, _cli_failure_reason(response, cli))

    match parse_findings_response(response.stdout, structured=structured):
        case ClientSuccess(data=list() as raw):
            pass
        case _:
            match _retry_review_reformat(adapter, response.stdout, worktree_path, structured):
                case ClientSuccess(data=list() as raw):
                    pass
                case _:
                    return _fail_review(ctx, "the review's answer could not be read")

    # Kept whole in the debug log: the response log keeps only its edges, and a run has
    # to be auditable from its own log.
    logger.debug("review_findings_parsed", findings_count=len(raw), findings=raw)
    kept, rejected = partition_findings_by_path(
        raw, {entry.path for entry in manifest.files}, _repo_file_checker(worktree_path)
    )
    if rejected:
        logger.warning("review_findings_unknown_path", dropped=len(rejected), rejected=rejected)

    ctx.textual.success_text(f"✓ Review complete · {len(kept)} finding(s)")
    if rejected:
        _render_rejected_paths(ctx, rejected)
    ctx.textual.end_step("success")
    return Success(
        "AI findings retrieved",
        metadata={
            "raw_findings": [to_finding_payload(item) for item in kept],
            "ai_findings_failed": False,
        },
    )


def normalize_findings(ctx: WorkflowContext) -> WorkflowResult:
    """
    Parse and validate raw AI output into Finding models.

    Accepts raw_findings as either a JSON string or a list of dicts.
    Each item is validated as a Finding model. Invalid items are skipped
    with a warning rather than failing the entire step.

    Inputs (from ctx.data):
        raw_findings (list | str): Raw AI output from ai_review_findings

    Outputs (saved to ctx.data):
        normalized_findings (List[Finding]): Validated Finding objects

    Returns:
        Success: The step completed.
        Error: The step failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Normalize Findings")

    raw = ctx.get("raw_findings")

    if raw is None:
        ctx.textual.error_text("No raw_findings in context (run ai_review_findings first)")
        ctx.textual.end_step("error")
        return Error("No raw_findings in context (run ai_review_findings first)")

    from ..models.review_models import Finding
    from pydantic import ValidationError
    import json

    # Parse JSON string if needed
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as e:
            ctx.textual.error_text(f"Failed to parse raw_findings JSON: {e}")
            ctx.textual.end_step("error")
            return Error(f"Failed to parse raw_findings JSON: {e}")

    if not isinstance(raw, list):
        ctx.textual.error_text(f"raw_findings must be a list, got {type(raw).__name__}")
        ctx.textual.end_step("error")
        return Error(f"raw_findings must be a list, got {type(raw).__name__}")

    findings: list[Finding] = []
    skipped = 0

    for i, item in enumerate(raw):
        try:
            findings.append(Finding.model_validate(item))
        except ValidationError as e:
            skipped += 1
            ctx.textual.dim_text(f"⚠ Finding {i + 1} invalid, skipping: {e.error_count()} error(s)")
            logger.debug("finding_validation_failed", index=i + 1, error=str(e))

    summary = f"✓ {len(findings)} finding(s) normalized"
    if skipped:
        summary += f" ({skipped} skipped)"
    ctx.textual.success_text(summary)
    ctx.textual.end_step("success")
    return Success("Findings normalized", metadata={"normalized_findings": findings})


def dedupe_findings(ctx: WorkflowContext) -> WorkflowResult:
    """
    Remove findings that duplicate existing PR comments.

    Uses the is_duplicate() validator to compare each finding against the
    existing_comments_index. A finding is a duplicate if it targets the same
    file, the same area (within 5 lines), and the same topic (same category
    or similar title).

    Inputs (from ctx.data):
        normalized_findings (List[Finding])
        existing_comments_index (List[ExistingCommentIndexEntry])

    Outputs (saved to ctx.data):
        deduped_findings (List[Finding]): Findings after duplicate removal

    Returns:
        Success: The step completed.
        Error: The step failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Deduplicate Findings")

    findings = ctx.get("normalized_findings")
    existing_index = ctx.get("existing_comments_index", [])

    if findings is None:
        ctx.textual.error_text("No normalized_findings in context (run normalize_findings first)")
        ctx.textual.end_step("error")
        return Error("No normalized_findings in context (run normalize_findings first)")

    from ..models.validators import is_duplicate

    deduped: list = []
    removed = 0
    removed_existing = 0
    removed_adjudicated = 0
    seen_keys: set[tuple[str, int | None, str]] = set()

    for finding in findings:
        is_dup = any(is_duplicate(finding, ex) for ex in existing_index)
        key = (finding.path, finding.line, finding.title.lower())
        if is_dup or key in seen_keys:
            removed += 1
            if is_dup:
                removed_existing += 1
                if any(ex.is_adjudicated and is_duplicate(finding, ex) for ex in existing_index):
                    removed_adjudicated += 1
            logger.debug(
                "finding_deduplicated",
                title=finding.title,
                path=finding.path,
                line=finding.line,
            )
        else:
            deduped.append(finding)
            seen_keys.add(key)

    deduped, collapsed = _collapse_derived_findings(deduped)
    removed += collapsed

    summary = f"✓ {len(deduped)} finding(s) ready"
    if removed:
        # Say WHY findings were dropped: "already commented on the PR" explains why a
        # re-run reports different things than the first pass — "duplicates removed"
        # does not.
        if removed_existing:
            summary += f" ({removed_existing} skipped: already commented on this PR"
            if removed > removed_existing:
                summary += f"; {removed - removed_existing} internal duplicate(s)"
            summary += ")"
        else:
            summary += f" ({removed} internal duplicate(s) removed)"
    ctx.textual.success_text(summary)
    # The taxonomy, not just the count: comparing runs, or judging whether a
    # prompt change helped, needs to know WHAT the model produced. A bare total
    # cannot distinguish five style nits from five correctness bugs.
    severities: dict = {}
    categories: dict = {}
    for finding in deduped:
        sev = getattr(finding, "severity", None)
        cat = getattr(finding, "category", None)
        sev = getattr(sev, "value", sev)
        cat = getattr(cat, "value", cat)
        severities[str(sev)] = severities.get(str(sev), 0) + 1
        categories[str(cat)] = categories.get(str(cat), 0) + 1

    logger.info(
        "findings_deduplicated",
        deduped_findings_count=len(deduped),
        findings_removed_due_to_existing_threads=removed_existing,
        findings_removed_due_to_adjudicated_threads=removed_adjudicated,
        severities=severities,
        categories=categories,
    )
    ctx.textual.end_step("success")
    return Success(
        "Findings deduplicated",
        metadata={"deduped_findings": deduped, "deduped_findings_count": len(deduped)},
    )


# ============================================================================
# PHASE 5: UI + SUBMIT
# ============================================================================


def build_new_comment_actions(ctx: WorkflowContext) -> WorkflowResult:
    """
    Convert deduplicated findings into ReviewActionProposal objects.

    Inputs (from ctx.data):
        deduped_findings (List[Finding])

    Outputs (saved to ctx.data):
        review_action_proposals (List[ReviewActionProposal])

    Returns:
        Success: The step completed.
        Skip: Nothing to do (no findings).
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Build Comment Actions")

    findings = ctx.get("deduped_findings", [])
    manifest = ctx.get("change_manifest")

    if not findings:
        ctx.textual.dim_text("No findings to convert into actions.")
        ctx.textual.end_step("skip")
        return Skip("No findings to submit")

    actions = build_new_comment_actions_operation(findings)
    manifest_files = {file.path: file for file in getattr(manifest, "files", [])}
    enriched_actions = []
    for action in actions:
        file_entry = manifest_files.get(action.path)
        enriched_actions.append(
            action.model_copy(
                update={
                    "file_status": str(file_entry.status) if file_entry else None,
                    "is_test_file": bool(file_entry.is_test) if file_entry else False,
                }
            )
        )
    actions = enriched_actions

    ctx.textual.success_text(f"✓ {len(actions)} action(s) ready for review")
    ctx.textual.end_step("success")
    return Success("Actions built", metadata={"review_action_proposals": actions})


def _release_review_worktree(ctx: WorkflowContext) -> None:
    """Remove the review worktree as soon as nothing will read from it again.

    The workflow's final cleanup step only runs when the workflow reaches it —
    abandoning the review at an interactive gate (exit button, quitting the app at
    the submit prompt) used to leave the worktree on disk. Failure here is fine:
    the final cleanup step remains as backstop.
    """
    if not ctx.get("worktree_created") or not ctx.get("worktree_path") or not ctx.git:
        return
    from ..operations import cleanup_worktree as cleanup_worktree_operation
    from ..operations import delete_review_refs

    if cleanup_worktree_operation(ctx.git, ctx.data["worktree_path"]):
        pr_number = ctx.get("selected_pr_number") or ctx.get("review_pr_number")
        if pr_number:
            delete_review_refs(ctx.git, pr_number)
        ctx.textual.dim_text("Review worktree removed (no longer needed).")
        ctx.data["worktree_created"] = False
        ctx.data["worktree_path"] = None
    else:
        logger.warning("early_worktree_release_failed", worktree_path=ctx.data.get("worktree_path"))


def validate_review_actions(ctx: WorkflowContext) -> WorkflowResult:
    """
    Present each ReviewActionProposal to the user for approval, editing, or skipping.

    Inputs (from ctx.data):
        review_action_proposals (List[ReviewActionProposal])

    Optional (from ctx.data):
        review_diff (str): Full PR diff for extracting diff context per comment

    Outputs (saved to ctx.data):
        approved_action_proposals (List[ReviewActionProposal])

    Returns:
        Success: The step completed.
        Skip: Nothing to do (none approved).
        Error: The step failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Validate & Approve Actions")

    actions: List[ReviewActionProposal] = ctx.get("review_action_proposals", [])

    if not actions:
        ctx.textual.dim_text("No actions to validate.")
        _release_review_worktree(ctx)
        ctx.textual.end_step("skip")
        return Skip("No actions to validate")

    diff = ctx.get("review_diff", "")
    review_threads: List[UICommentThread] = ctx.get("review_threads", [])
    diff_manager = ctx.get("review_diff_manager")

    # Sort by severity: blocking → important → nit
    severity_order = {"blocking": 0, "important": 1, "nit": 2}
    resolved_actions = resolve_action_anchors(actions, diff, diff_manager=diff_manager)

    sorted_actions = sorted(
        resolved_actions,
        key=lambda a: severity_order.get(a.severity.value if a.severity else "", 99),
    )

    # Precompute every action's code context NOW: anchors are resolved and the diff
    # hunks / file excerpts below are the last reads from the worktree. Releasing it
    # before the interactive loop means abandoning the review mid-gate (exit button,
    # quitting the app at the submit prompt) can no longer leave a stale worktree —
    # the final cleanup_worktree step becomes a no-op backstop.
    prepared: List[tuple] = []
    for action in sorted_actions:
        diff_hunk = extract_diff_hunk_for_action(action, diff, diff_manager=diff_manager)
        # Unanchored findings have no diff hunk by definition — read the real file so the
        # user judges the finding against its code instead of a bare assertion.
        file_excerpt = extract_file_excerpt_for_action(action, diff_manager=diff_manager)
        prepared.append((action, diff_hunk, file_excerpt))
    _release_review_worktree(ctx)

    approved: List[ReviewActionProposal] = []
    skipped = 0
    exit_requested = False

    for idx, (action, diff_hunk, file_excerpt) in enumerate(prepared):
        if exit_requested:
            break

        current = action

        while True:
            choice = _show_review_action_and_get_decision(
                ctx, current, diff_hunk or "", idx, len(sorted_actions),
                review_threads=review_threads,
                file_excerpt=file_excerpt,
            )

            if choice == "exit":
                exit_requested = True
                ctx.textual.warning_text(
                    f"Exiting validation. Approved {len(approved)}, skipped {skipped}."
                )
                break

            elif choice == "approve":
                approved.append(current)
                break

            elif choice == "edit":
                ctx.textual.text("")
                new_body = ctx.textual.ask_multiline(
                    "Edit the review comment:",
                    default=current.body,
                )
                if new_body and new_body.strip():
                    approved.append(current.model_copy(update={"body": new_body.strip()}))
                else:
                    ctx.textual.warning_text("Empty body, comment skipped")
                    skipped += 1
                break

            else:  # skip
                skipped += 1
                break

    if not approved:
        ctx.textual.dim_text("No actions approved.")
        ctx.textual.end_step("skip")
        return Skip("No approved review actions")

    ctx.textual.success_text(f"✓ {len(approved)} action(s) approved, {skipped} skipped")
    ctx.textual.end_step("success")
    return Success(
        f"{len(approved)} action(s) approved",
        metadata={"approved_action_proposals": approved},
    )


def _detect_submit_time_sha_drift(ctx: WorkflowContext, pr_number: int, reviewed_sha: str):
    """
    Re-read the PR's head SHA and compare it with the one the review was prepared against.

    The bundle's SHA is captured minutes earlier, before the user inspects findings. A push
    in that window invalidates every resolved line, so this is checked at submit time
    rather than trusted from the bundle.
    """
    from ..operations.review_action_operations import detect_head_sha_drift

    current_sha = ""
    match ctx.github.get_pr_commit_sha(pr_number):
        case ClientSuccess(data=sha):
            current_sha = (sha or "").strip()
        case ClientError(error_message=err):
            # Unverifiable is not the same as drifted: the publish gate still validates
            # every line against the diff, so proceed rather than block the submission.
            logger.debug("submit_sha_recheck_failed", pr_number=pr_number, error=err)

    drift = detect_head_sha_drift(reviewed_sha, current_sha)
    logger.debug(
        "submit_sha_drift_check",
        pr_number=pr_number,
        reviewed_sha=drift.reviewed_sha,
        current_sha=drift.current_sha,
        drifted=drift.drifted,
    )
    return drift


def _resolve_drift_changed_files(ctx: WorkflowContext, drift) -> Optional[set]:
    """Return the paths the drift's push touched, or None when unknowable.

    The new head only exists locally after a fetch — the push happened after the
    review's own fetch. Any failure returns None so the caller falls back to
    degrading every comment, never to publishing stale anchors.
    """
    if not ctx.git or not drift.reviewed_sha or not drift.current_sha:
        return None
    match ctx.git.fetch(all=True):
        case ClientError(error_message=err):
            # The new head may already be present from an earlier fetch, so let
            # get_changed_files decide — it returns an error (→ None) if not.
            logger.warning("drift_fetch_failed", error=err)
        case _:
            pass
    match ctx.git.get_changed_files(drift.reviewed_sha, drift.current_sha):
        case ClientSuccess(data=paths):
            return set(paths)
        case ClientError(error_message=err):
            logger.warning(
                "drift_changed_files_unavailable",
                reviewed_sha=drift.reviewed_sha,
                current_sha=drift.current_sha,
                error=err,
            )
            return None
    return None


def submit_review_actions(ctx: WorkflowContext) -> WorkflowResult:
    """
    Submit approved ReviewActionProposal objects to GitHub.

    Handles resolve_thread actions directly, then submits new_comment and
    reply_to_thread actions as a GitHub draft review.

    Inputs (from ctx.data):
        approved_action_proposals (List[ReviewActionProposal])
        review_pr_number (int)

    Optional (from ctx.data):
        review_commit_sha (str): Head commit SHA (fetched if missing)
        review_diff (str): Full PR diff for inline comment validation

    Returns:
        Success: The step completed.
        Skip: Nothing to do (no approved actions).
        Error: The step failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Submit Review")

    # The whole review's AI spend, logged on the way IN rather than at one of this
    # step's many exits: submitting makes no AI calls, so by now every call is
    # accounted for, and one call site cannot drift out of sync with the others.
    log_review_ai_cost(ctx, scope="review")

    approved: List[ReviewActionProposal] = ctx.get("approved_action_proposals", [])
    pr_number = ctx.get("review_pr_number")
    commit_sha = ctx.get("review_commit_sha", "")
    diff = ctx.get("review_diff", "")
    diff_manager = ctx.get("review_diff_manager")

    if not pr_number:
        ctx.textual.error_text("No PR number in context")
        ctx.textual.end_step("error")
        return Error("No PR number in context")

    if not ctx.github:
        ctx.textual.error_text("GitHub client not available")
        ctx.textual.end_step("error")
        return Error("GitHub client not available")

    if not approved:
        ctx.textual.dim_text("No approved actions — you can still submit a review decision.")

    # Handle thread actions first (direct API, outside the review draft)
    resolve_actions = [a for a in approved if a.action_type == ReviewActionType.RESOLVE_THREAD]
    reply_actions = [a for a in approved if a.action_type == ReviewActionType.REPLY_TO_THREAD]
    comment_actions = [a for a in approved if a.action_type == ReviewActionType.NEW_COMMENT]

    for action in resolve_actions:
        if not action.thread_id:
            continue
        with ctx.textual.loading("Resolving thread..."):
            result = ctx.github.resolve_review_thread(action.thread_id)
        match result:
            case ClientSuccess():
                ctx.textual.success_text("✓ Thread resolved")
            case ClientError(error_message=err):
                ctx.textual.warning_text(f"Could not resolve thread: {err}")

    for action in reply_actions:
        if not action.comment_id or not pr_number:
            continue
        with ctx.textual.loading("Posting reply to comment..."):
            result = ctx.github.reply_to_comment(pr_number, action.comment_id, action.body)
        match result:
            case ClientSuccess():
                ctx.textual.success_text("✓ Reply posted")
            case ClientError(error_message=err):
                ctx.textual.warning_text(f"Could not post reply: {err}")

    # Get commit SHA if not available (needed for inline comments)
    if not commit_sha and comment_actions:
        with ctx.textual.loading("Fetching latest commit SHA..."):
            sha_result = ctx.github.get_pr_commit_sha(pr_number)
        match sha_result:
            case ClientSuccess(data=sha):
                commit_sha = sha
            case ClientError(error_message=err):
                ctx.textual.error_text("No commit SHA available — cannot submit inline comments")
                ctx.textual.end_step("error")
                return Error(f"Missing commit SHA for inline review: {err}")

    # The anchors were resolved against commit_sha's diff. If the PR has been pushed to
    # since, inline lines on the files that push touched describe code that moved —
    # degrade those to the review body rather than publish comments on the wrong lines.
    # Anchors on files the push did NOT touch are still exact, so they stay inline.
    force_general_body = False
    force_general_paths: set = set()
    if comment_actions:
        drift = _detect_submit_time_sha_drift(ctx, pr_number, commit_sha)
        if drift.drifted:
            ctx.textual.warning_text(f"⚠ PR head changed: {drift.message}")
            ctx.textual.dim_text(
                f"reviewed: {drift.reviewed_sha[:8]} · current: {drift.current_sha[:8]}"
            )
            pushed_paths = _resolve_drift_changed_files(ctx, drift)
            comment_paths = {a.path for a in comment_actions if a.path}
            if pushed_paths is not None:
                force_general_paths = comment_paths & pushed_paths
                # Untouched files have identical anchors under the new head, so the
                # review can anchor everything to it instead of the stale SHA.
                commit_sha = drift.current_sha
                logger.debug(
                    "sha_drift_scoped_to_files",
                    pr_number=pr_number,
                    pushed_files=len(pushed_paths),
                    comments_degraded=len(force_general_paths),
                    comments_kept_inline=len(comment_paths - force_general_paths),
                )
            if pushed_paths is None:
                ctx.textual.text(
                    f"The {len(comment_actions)} comment(s) will go in the review body instead "
                    "of inline, since their line numbers no longer match the PR's diff."
                )
                force_general_body = True
            elif force_general_paths:
                ctx.textual.text(
                    f"The push touched {len(force_general_paths)} of the commented file(s): "
                    "their comment(s) will go in the review body; the rest stay inline."
                )
                for path in sorted(force_general_paths):
                    ctx.textual.dim_text(f"  {path}")
            else:
                ctx.textual.dim_text(
                    "The push did not touch any commented file — all comments stay inline."
                )
            if (force_general_body or force_general_paths) and not ctx.textual.ask_confirm(
                "Publish the review anyway?", default=True
            ):
                ctx.textual.warning_text("Review cancelled")
                ctx.textual.end_step("skip")
                return Skip("User cancelled after head SHA drift")

    # Show AI's opinion and prepare action options
    ctx.textual.text("")
    if comment_actions:
        ctx.textual.text(f"📋 Found {len(comment_actions)} issue(s) to address")
        ctx.textual.text(f"Ready to submit {len(comment_actions)} comment(s) on PR #{pr_number}")
        ctx.textual.text("")

        # With findings - offer Comment or Request Changes
        event_options = [
            OptionItem(value="COMMENT", title="💬 Comment", description="Post comments without approval decision"),
            OptionItem(value="REQUEST_CHANGES", title="🔴 Request Changes", description="Block merge until changes are made"),
        ]
    elif ctx.get("ai_findings_failed", False):
        # The AI review never produced findings, so "no findings" says nothing about the
        # PR — don't present it as clean or offer to approve it. Keyed on the review step's
        # own flag, not on `raw_findings`: Thread Resolution publishes through this step
        # without running a review.
        ctx.textual.warning_text("⚠ The AI review did not run — this PR has NOT been reviewed")
        ctx.textual.text("")

        event_options = [
            OptionItem(value="COMMENT", title="💬 Comment", description="Post a general comment"),
            OptionItem(value="REQUEST_CHANGES", title="🔴 Request Changes", description="Block merge until changes are made"),
        ]
    else:
        ctx.textual.success_text("✅ No issues found - PR looks good and can be approved")
        ctx.textual.text("")

        # No findings - offer all options
        event_options = [
            OptionItem(value="APPROVE", title="✅ Approve", description="Approve the PR"),
            OptionItem(value="COMMENT", title="💬 Comment", description="Post a general comment"),
            OptionItem(value="REQUEST_CHANGES", title="🔴 Request Changes", description="Block merge until changes are made"),
        ]

    try:
        event = ctx.textual.ask_option("Select review type:", event_options)
    except Exception as e:
        ctx.textual.error_text(str(e))
        ctx.textual.end_step("error")
        return Error(str(e))

    if not event:
        ctx.textual.warning_text("Review cancelled")
        ctx.textual.end_step("skip")
        return Skip("User cancelled review submission")

    # Optional general body
    add_body = ctx.textual.ask_confirm("Add a general review comment (optional)?", default=False)
    review_body = ""
    if add_body:
        review_body = ctx.textual.ask_multiline("General review comment:", default="")

    # Build payload from comment actions
    payload = build_review_action_payload(
        comment_actions,
        commit_sha,
        diff,
        diff_manager=diff_manager,
        force_general_body=force_general_body,
        force_general_paths=force_general_paths,
    )

    if review_body and review_body.strip():
        existing_body = payload.get("body", "")
        payload["body"] = (existing_body + "\n\n" + review_body.strip()).strip()

    has_inline_comments = bool(payload.get("comments"))
    has_body = bool(payload.get("body"))
    is_empty_payload = not has_inline_comments and not has_body
    # Human label for the GitHub review event ('COMMENT'/'APPROVE'/'REQUEST_CHANGES').
    event_labels = {
        "COMMENT": "Comment",
        "APPROVE": "Approve",
        "REQUEST_CHANGES": "Request Changes",
    }
    event_label = event_labels.get(event, event)

    if is_empty_payload:
        ctx.textual.dim_text("Submitting review without comments...")
        with ctx.textual.loading("Submitting review..."):
            submit_result = ctx.github.submit_review(pr_number, None, event, "")
        match submit_result:
            case ClientSuccess():
                ctx.textual.success_text(f"✓ Review submitted ({event_label}) on PR #{pr_number}")
                ctx.textual.end_step("success")
                return Success(f"Review submitted on PR #{pr_number}")
            case ClientError(error_message=err, error_code="PENDING_REVIEW_EXISTS"):
                ctx.textual.warning_text(err)
                ctx.textual.end_step("error")
                return Error(err)
            case ClientError(error_message=err):
                ctx.textual.error_text(f"Failed to submit review: {err}")
                ctx.textual.end_step("error")
                return Error(f"Failed to submit review: {err}")

    with ctx.textual.loading("Creating review..."):
        draft_result = ctx.github.create_draft_review(pr_number, payload)

    match draft_result:
        case ClientSuccess(data=review_id):
            ctx.textual.success_text(f"✓ Review #{review_id} created")
        case ClientError(error_message=err):
            logger.error(
                "draft_review_creation_failed",
                pr_number=pr_number,
                error=err,
                inline_comment_count=len(payload.get("comments", [])),
            )
            if payload.get("comments"):
                ctx.textual.warning_text(
                    "GitHub rejected the review — checking which comments it will accept…"
                )
                filtered_payload, rejected_comments = _filter_invalid_inline_comments(ctx, pr_number, payload)
                if rejected_comments:
                    rejection_breakdown: dict[str, int] = {}
                    for comment in rejected_comments:
                        kind = classify_github_review_rejection(comment.get("error", ""))
                        rejection_breakdown[kind] = rejection_breakdown.get(kind, 0) + 1
                    ctx.textual.warning_text(
                        f"⚠ {len(rejected_comments)} comment(s) can't be placed inline and will be "
                        "added to the review body instead:"
                    )
                    for comment in rejected_comments:
                        ctx.textual.dim_text(
                            f"  {comment.get('path')}:{comment.get('line')}"
                        )
                    logger.debug(
                        "inline_comments_filtered_after_422",
                        pr_number=pr_number,
                        inline_candidates_total=len(payload.get("comments", [])),
                        inline_candidates_validated=len(filtered_payload.get("comments", [])),
                        inline_candidates_rejected=len(rejected_comments),
                        inline_submit_success_rate=(
                            len(filtered_payload.get("comments", [])) / len(payload.get("comments", []))
                            if payload.get("comments")
                            else 0.0
                        ),
                        rejected_count=len(rejected_comments),
                        valid_count=len(filtered_payload.get("comments", [])),
                        rejection_breakdown=rejection_breakdown,
                    )
                    if filtered_payload.get("comments") or filtered_payload.get("body"):
                        payload = filtered_payload
                        with ctx.textual.loading("Retrying review creation with valid comments only..."):
                            retry_result = ctx.github.create_draft_review(pr_number, payload)
                        match retry_result:
                            case ClientSuccess(data=review_id):
                                ctx.textual.success_text(
                                    f"✓ Review #{review_id} created without the rejected comment(s)"
                                )
                            case ClientError(error_message=retry_err):
                                ctx.textual.error_text(f"Failed to create review: {retry_err}")
                                ctx.textual.end_step("error")
                                return Error(f"Failed to create draft review: {retry_err}")
                    else:
                        ctx.textual.error_text(f"Failed to create review: {err}")
                        ctx.textual.end_step("error")
                        return Error(f"Failed to create draft review: {err}")
                else:
                    ctx.textual.error_text(f"Failed to create review: {err}")
                    ctx.textual.end_step("error")
                    return Error(f"Failed to create draft review: {err}")
            else:
                ctx.textual.error_text(f"Failed to create review: {err}")
                ctx.textual.end_step("error")
                return Error(f"Failed to create draft review: {err}")

    with ctx.textual.loading("Submitting review..."):
        submit_result = ctx.github.submit_review(
            pr_number, review_id, event, payload.get("body", "")
        )

    match submit_result:
        case ClientSuccess():
            ctx.textual.success_text(
                f"✓ Review submitted ({event_label}) on PR #{pr_number}"
                + (f" with {len(comment_actions)} comment(s)" if comment_actions else "")
            )
            # The outcome of the whole workflow existed only on screen. Without
            # it a log can say what the model proposed but never what was
            # actually posted, which is the half that says whether a review was
            # any good.
            logger.info(
                "review_published",
                pr_number=pr_number,
                review_event=event,
                inline_comments=len(payload.get("comments") or []),
                has_body=bool(payload.get("body")),
                actions_offered=len(comment_actions),
            )
            ctx.textual.end_step("success")
            return Success(f"Review submitted on PR #{pr_number}")
        case ClientError(error_message=err, error_code="PENDING_REVIEW_EXISTS"):
            ctx.textual.warning_text(err)
            ctx.textual.end_step("error")
            return Error(err)
        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to submit review: {err}")
            ctx.textual.end_step("error")
            return Error(f"Failed to submit review: {err}")


# ============================================================================
# PHASE 6: THREAD RESOLUTION PIPELINE
# ============================================================================


def build_thread_review_candidates(ctx: WorkflowContext) -> WorkflowResult:
    """
    Select open inline threads worth AI analysis.

    Filters out:
    - General comments (no GraphQL resolve API)
    - Already-resolved threads
    - Threads where the PR author has not replied (reviewer is waiting for response)

    Only includes threads where the last comment is from the PR author,
    indicating they have responded to the review.

    Inputs (from ctx.data):
        review_threads (List[UICommentThread]): Unresolved inline review threads
        review_pr (UIPullRequest): PR object with author info
        review_current_user (str): GitHub login running Titan

    Outputs (saved to ctx.data):
        thread_review_candidates (List[ThreadReviewCandidate])

    Returns:
        Success: The step completed.
        Skip: Nothing to do (no candidates).
        Error: The step failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Build Thread Review Candidates")

    threads = ctx.get("review_threads", [])
    pr = ctx.get("review_pr")
    review_current_user = ctx.get("review_current_user")

    if not pr:
        ctx.textual.dim_text("No PR info available")
        ctx.textual.end_step("skip")
        return Skip("No PR data in context")

    if not review_current_user:
        ctx.textual.error_text("Current GitHub user not available")
        ctx.textual.end_step("error")
        return Error("Current GitHub user not available")

    candidates = build_thread_review_candidates_operation(
        threads,
        pr.author_name,
        review_current_user,
    )

    if not candidates:
        if not threads:
            ctx.textual.dim_text("No open inline threads on this PR")
        else:
            ctx.textual.dim_text(
                f"No open threads created by @{review_current_user} with author replies yet"
            )
        ctx.textual.end_step("skip")
        return Skip("No threads to review")

    ctx.data["thread_review_candidates"] = candidates
    ctx.textual.success_text(
        f"✓ {len(candidates)} thread(s) created by @{review_current_user} with author replies selected"
    )
    ctx.textual.end_step("success")
    return Success("Thread candidates built", metadata={"thread_review_candidates_count": len(candidates)})


def build_thread_review_contexts(ctx: WorkflowContext) -> WorkflowResult:
    """
    Enrich thread candidates with diff hunk context and full reply history.

    For each candidate, extracts the diff hunk near the commented line,
    collects all replies from the full UICommentThread object, and attaches
    remote context for commit SHAs referenced in those replies.

    Inputs (from ctx.data):
        thread_review_candidates (List[ThreadReviewCandidate])
        review_threads (List[UICommentThread]): For extracting reply history
        review_diff (str): Full PR unified diff

    Requires:
        ctx.github: Optional GitHub client used to inspect referenced commits.

    Outputs (saved to ctx.data):
        thread_review_contexts (List[ThreadReviewContext])

    Returns:
        Success: The step completed.
        Skip: Nothing to do (no candidates).
        Error: The step failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Build Thread Review Contexts")

    candidates = ctx.get("thread_review_candidates")
    threads = ctx.get("review_threads", [])
    diff = ctx.get("review_diff", "")

    if not candidates:
        ctx.textual.dim_text("No thread candidates available")
        ctx.textual.end_step("skip")
        return Skip("No thread_review_candidates in context")

    contexts = build_thread_review_contexts_operation(candidates, threads, diff)
    candidate_ids = {candidate.thread_id for candidate in candidates}
    candidate_threads = [thread for thread in threads if thread.thread_id in candidate_ids]
    review_pr = ctx.get("review_pr")
    commit_contexts_by_thread = _load_referenced_commit_contexts(ctx, candidate_threads, review_pr)
    if commit_contexts_by_thread:
        contexts = [
            context.model_copy(
                update={
                    "referenced_commits": commit_contexts_by_thread.get(
                        context.thread_id,
                        [],
                    )
                }
            )
            for context in contexts
        ]

    ctx.data["thread_review_contexts"] = contexts
    referenced_commit_count = sum(len(context.referenced_commits) for context in contexts)
    summary = f"✓ {len(contexts)} thread context(s) built"
    if referenced_commit_count:
        summary += f" ({referenced_commit_count} referenced commit context(s))"
    ctx.textual.success_text(summary)
    ctx.textual.end_step("success")
    return Success("Thread contexts built", metadata={"thread_review_contexts_count": len(contexts)})


@declare_ai_usage(
    task="thread_resolution",
    executes=[AIProviderType.CLI_HEADLESS],
    enforces=True,
)
def ai_thread_resolution(ctx: WorkflowContext) -> WorkflowResult:
    """
    AI call: decide what to do with each open thread.

    Splits thread contexts into prompt-budget-bound batches (see
    batch_thread_review_contexts) and sends each batch — original comment +
    replies + current code + referenced commits, all untouched — to the
    selected headless CLI. The AI decides per thread: resolved / insist /
    reply / skip. Batches run sequentially and their decisions are aggregated;
    a batch that fails (CLI error or parse error) is skipped without aborting
    the remaining batches.

    On total failure (no batch produced usable output), falls back to empty
    decisions (no actions).

    Which CLI runs it comes from the `thread_resolution` task preference
    (AI Configuration screen), not from the workflow.

    Inputs (from ctx.data):
        thread_review_contexts (List[ThreadReviewContext])

    Outputs (saved to ctx.data):
        raw_thread_decisions (list): Raw AI output aggregated across batches, before normalization

    Returns:
        Success: The step completed.
        Error: The step failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("AI Thread Resolution")

    contexts = ctx.get("thread_review_contexts")
    project_root = ctx.data.get("project_root")

    if not contexts:
        ctx.textual.dim_text("No thread contexts available")
        ctx.textual.end_step("skip")
        return Skip("No thread_review_contexts in context")

    adapter, route_note, ai_off = _resolve_review_adapter(ctx, ai_thread_resolution)

    if not adapter:
        ctx.textual.warning_text(
            f"{route_note or 'No headless CLI available'} — skipping AI thread resolution"
        )
        ctx.data["raw_thread_decisions"] = []
        ctx.textual.end_step("success")
        return Success(
            f"No decisions ({_route_failure_reason(route_note, ai_off)})",
            metadata={"raw_thread_decisions": []},
        )

    _announce_review_adapter(ctx, adapter)

    # Split into batches so one call never has to carry every open thread at
    # once — each thread's full conversation/hunk/commit context stays intact,
    # only the number of threads sharing a single AI call is bounded.
    batches = batch_thread_review_contexts(contexts)
    cli_display = adapter.cli_name.value.capitalize()
    ctx.textual.dim_text(
        f"Reviewing {len(contexts)} thread(s) in {len(batches)} batch(es) with {cli_display}"
    )

    aggregated_raw: list = []
    any_batch_failed = False

    for batch_index, batch in enumerate(batches, start=1):
        batch_label = f"batch {batch_index}/{len(batches)}"
        prompt = build_thread_resolution_prompt(batch)

        _log_ai_prompt(
            step_name="ai_thread_resolution",
            cli_name=adapter.cli_name.value,
            prompt=prompt,
            batch_index=batch_index,
            batch_count=len(batches),
            thread_count=len(batch),
        )

        adapter_started_at = time.monotonic()
        with ctx.textual.loading(
            f"Asking {cli_display} to analyse {batch_label} ({len(batch)} thread(s))…"
        ):
            response = run_interruptible(
                lambda: adapter.execute(prompt, cwd=project_root, timeout=300)
            )
        adapter_duration_seconds = time.monotonic() - adapter_started_at
        logger.info(
            "thread_resolution_adapter_call",
            cli=adapter.cli_name.value,
            batch_index=batch_index,
            batch_count=len(batches),
            thread_count=len(batch),
            prompt_actual_chars=len(prompt),
            duration_seconds=round(adapter_duration_seconds, 3),
            exit_code=response.exit_code,
            timed_out=response.exit_code == 124,
        )
        _log_ai_response(
            step_name="ai_thread_resolution",
            cli_name=adapter.cli_name.value,
            stdout=response.stdout,
            stderr=response.stderr,
            exit_code=response.exit_code,
            batch_index=batch_index,
            batch_count=len(batches),
        )

        if not response.succeeded:
            any_batch_failed = True
            ctx.textual.warning_text(
                f"{batch_label}: CLI call failed "
                f"({_cli_failure_reason(response, adapter.cli_name.value)}) — skipped"
            )
            if response.stderr:
                ctx.textual.dim_text(response.stderr[:200])
            continue

        match extract_json_payload(response.stdout, kind="array"):
            case ClientError(error_message=err):
                any_batch_failed = True
                ctx.textual.warning_text(f"{batch_label}: decisions parsing failed ({err}) — skipped")
                continue
            case ClientSuccess(data=raw):
                aggregated_raw.extend(raw)

    ctx.data["raw_thread_decisions"] = aggregated_raw

    if not aggregated_raw:
        status = "No decisions (all batches failed)" if any_batch_failed else "No decisions"
        ctx.textual.warning_text(status)
        ctx.textual.end_step("success")
        return Success(status, metadata={"raw_thread_decisions": []})

    summary = f"✓ AI returned {len(aggregated_raw)} thread decision(s)"
    if any_batch_failed:
        summary += " (some batches failed — partial results)"
    ctx.textual.success_text(summary)
    ctx.textual.end_step("success")
    return Success(
        "AI thread decisions retrieved",
        metadata={"raw_thread_decisions_count": len(aggregated_raw)},
    )


def normalize_thread_decisions(ctx: WorkflowContext) -> WorkflowResult:
    """
    Parse and validate raw AI output into ThreadDecision models.

    Accepts raw_thread_decisions as a list of dicts or a JSON string.
    Each item is validated as a ThreadDecision model. Invalid items are
    skipped with a warning rather than failing the entire step.

    Inputs (from ctx.data):
        raw_thread_decisions (list | str): Raw AI output from ai_thread_resolution

    Outputs (saved to ctx.data):
        thread_decisions (List[ThreadDecision]): Validated ThreadDecision objects

    Returns:
        Success: The step completed.
        Error: The step failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Normalize Thread Decisions")

    raw = ctx.get("raw_thread_decisions")

    if raw is None:
        ctx.textual.dim_text("No thread decisions to normalize")
        ctx.textual.end_step("skip")
        return Skip("No raw_thread_decisions in context")

    from ..models.review_models import ThreadDecision
    from pydantic import ValidationError
    import json

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as e:
            ctx.textual.error_text(f"Failed to parse raw_thread_decisions JSON: {e}")
            ctx.textual.end_step("error")
            return Error(f"Failed to parse raw_thread_decisions JSON: {e}")

    if not isinstance(raw, list):
        ctx.textual.error_text(f"raw_thread_decisions must be a list, got {type(raw).__name__}")
        ctx.textual.end_step("error")
        return Error(f"raw_thread_decisions must be a list, got {type(raw).__name__}")

    decisions: list[ThreadDecision] = []
    skipped = 0
    auto_resolved = 0

    for i, item in enumerate(raw):
        try:
            decision = ThreadDecision.model_validate(item)

            # Validate: if decision is "reply" or "insist" but suggested_reply is empty,
            # convert to "resolved" (avoid posting empty comments)
            if decision.decision in (ThreadDecisionType.REPLY, ThreadDecisionType.INSIST):
                reply_body = (decision.suggested_reply or "").strip()
                reasoning = (decision.reasoning or "").strip()

                if not reply_body:
                    # Try to use reasoning as fallback, otherwise convert to skip
                    if reasoning and len(reasoning) > 10:
                        # Use reasoning as the reply body
                        ctx.textual.dim_text(f"⚠ Decision {i + 1}: using reasoning as reply")
                        decision = decision.model_copy(update={"suggested_reply": reasoning})
                    else:
                        # Both empty - convert to skip
                        ctx.textual.dim_text(f"⚠ Decision {i + 1}: empty reply → skip")
                        decision = decision.model_copy(
                            update={
                                "decision": ThreadDecisionType.SKIP,
                                "suggested_reply": None,
                            }
                        )
                        auto_resolved += 1

            # Ensure suggested_reply is None for "resolved" and "skip"
            if decision.decision in (ThreadDecisionType.RESOLVED, ThreadDecisionType.SKIP):
                if decision.suggested_reply:
                    decision = decision.model_copy(update={"suggested_reply": None})

            decisions.append(decision)
        except ValidationError as e:
            skipped += 1
            ctx.textual.dim_text(f"⚠ Decision {i + 1} invalid, skipping: {e.error_count()} error(s)")
            logger.debug("thread_decision_validation_failed", index=i + 1, error=str(e))

    ctx.data["thread_decisions"] = decisions

    summary = f"✓ {len(decisions)} decision(s) normalized"
    if auto_resolved:
        summary += f" ({auto_resolved} empty replies → resolved)"
    if skipped:
        summary += f" ({skipped} skipped)"
    ctx.textual.success_text(summary)
    ctx.textual.end_step("success")
    return Success("Thread decisions normalized", metadata={
        "thread_decisions_count": len(decisions),
        "auto_resolved_empty_replies": auto_resolved
    })


def build_thread_actions(ctx: WorkflowContext) -> WorkflowResult:
    """
    Transform ThreadDecision objects into ReviewActionProposal objects.

    Maps AI decisions to concrete GitHub actions:
    - resolved → resolve_thread (mark thread as resolved via GraphQL)
    - insist / reply → reply_to_thread (post a follow-up comment via REST API)
    - skip → (no action created)

    Saves results under the same key as new_findings workflow so that
    validate_review_actions and submit_review_actions can be reused directly.

    Inputs (from ctx.data):
        thread_decisions (List[ThreadDecision])
        thread_review_contexts (List[ThreadReviewContext])

    Outputs (saved to ctx.data):
        review_action_proposals (List[ReviewActionProposal])

    Returns:
        Success: The step completed.
        Skip: Nothing to do (no actionable decisions).
        Error: The step failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Build Thread Actions")

    decisions = ctx.get("thread_decisions")
    contexts = ctx.get("thread_review_contexts", [])

    if decisions is None:
        ctx.textual.dim_text("No thread decisions available")
        ctx.textual.end_step("skip")
        return Skip("No thread_decisions in context")

    actions = build_thread_actions_operation(decisions, contexts)

    if not actions:
        ctx.textual.dim_text("No actionable thread decisions")
        ctx.textual.end_step("skip")
        return Skip("No actionable thread decisions")

    ctx.data["review_action_proposals"] = actions

    resolve_count = sum(1 for a in actions if a.action_type == ReviewActionType.RESOLVE_THREAD)
    reply_count = sum(1 for a in actions if a.action_type == ReviewActionType.REPLY_TO_THREAD)
    summary_parts = []
    if resolve_count:
        summary_parts.append(f"{resolve_count} resolve")
    if reply_count:
        summary_parts.append(f"{reply_count} reply")
    ctx.textual.success_text(f"✓ {len(actions)} action(s) built: {', '.join(summary_parts)}")
    ctx.textual.end_step("success")
    return Success("Thread actions built", metadata={"thread_actions_count": len(actions)})
