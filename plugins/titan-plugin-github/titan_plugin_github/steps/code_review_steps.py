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
from ..managers.prompt_budget_manager import get_prompt_budget_manager
from ..models.review_enums import ReviewActionType, ThreadDecisionType
from ..models.review_models import (
    ReferencedCommitContext,
    ReviewActionProposal,
    ReviewBudget,
)
from ..models.review_profile_models import ReviewProfile
from ..models.view import UICommentThread, UIPullRequest
from ..operations.review_strategy_operations import deep_call_timeout_seconds, review_budget
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
        build_comment_review_context,
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

# How many findings batches run against the CLI at once. The review is ONE session, so
# this only matters when a timed-out session is split and its halves re-run. Zero token
# cost, only wall time; kept low because each worker is a full CLI session and provider
# rate limits apply.
FINDINGS_BATCH_CONCURRENCY = 2


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
        Success, Exit (no PRs or cancelled), or Error
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

    Requires (from ctx.data):
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
        Success, Skip (empty diff), or Error
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

    Requires (from ctx.data):
        review_pr (UIPullRequest): Pull request details
        review_changed_files_with_stats (List[UIFileChange]): Files with add/del stats

    Outputs (saved to ctx.data):
        change_manifest (ChangeManifest): Structured PR context

    Returns:
        Success or Error
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
            pr, files, _get_review_profile(ctx), churn_by_path=churn_by_path
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

    Requires (from ctx.data):
        review_threads (List[UICommentThread]): Inline review threads
        review_general_comments (List[UICommentThread]): General PR-level comments

    Outputs (saved to ctx.data):
        existing_comments_index (List[ExistingCommentIndexEntry])

    Returns:
        Success
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Build Existing Comments Index")

    threads = ctx.get("review_threads", [])
    general = ctx.get("review_general_comments", [])
    changed_files = ctx.get("review_changed_files_with_stats", [])

    try:
        index = build_existing_comments_index_operation(threads, general)
        is_smallish_pr = len(changed_files) <= 8
        comment_context = build_comment_review_context(
            threads,
            general,
            max_entries=4 if is_smallish_pr else 8,
            max_chars=900 if is_smallish_pr else 1800,
            include_resolved=False,
            bug_risk_only=True,
        )
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
        comments_for_prompt_count=len(comment_context),
        dedupe_comment_count=len(index),
        resolved_comments_count=resolved_count,
        unresolved_comments_count=len(index) - resolved_count,
        adjudicated_threads_count=adjudicated_count,
        filtered_out_comment_entries=max(0, len(index) - len(comment_context)),
    )
    ctx.textual.end_step("success")
    return Success(
        "Comments index built",
        metadata={
            "existing_comments_index": index,
            "comment_review_context": comment_context,
        },
    )


def build_review_checklist(ctx: WorkflowContext) -> WorkflowResult:
    """
    Assemble the review checklist for this PR.

    Delegates checklist resolution to ChecklistManager so project-specific
    checklist loading can evolve without changing workflow orchestration.

    Outputs (saved to ctx.data):
        review_checklist (List[ReviewChecklistItem])

    Returns:
        Success
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Build Review Checklist")

    if not ctx.github_managers:
        ctx.textual.error_text("GitHub managers are not available in workflow context.")
        ctx.textual.end_step("error")
        return Error("GitHub managers are not available in workflow context.")

    # resolve() rather than the plain getters: it reports the SOURCE and what the
    # project's file changed, which is what makes a merged configuration inspectable
    # instead of something the user has to trust.
    checklist_resolution = ctx.github_managers.checklist.resolve()
    profile_resolution = ctx.github_managers.review_profile.resolve()
    checklist = checklist_resolution.checklist
    review_profile = profile_resolution.profile
    ctx.data["review_checklist"] = checklist
    ctx.data["review_profile"] = review_profile

    _render_review_config(ctx, profile_resolution, checklist_resolution)

    manifest = ctx.get("change_manifest")
    profile_path = profile_resolution.path
    checklist_path = checklist_resolution.path
    logger.info(
        "review_config_applied_to_pr",
        profile_source=profile_resolution.source,
        checklist_source=checklist_resolution.source,
        manifest_files=len(manifest.files) if manifest else 0,
        offered_checklist_count=len(checklist),
    )
    logger.debug(
        "review_config_applied_detail",
        project_root=str(ctx.data.get("project_root")) if ctx.data.get("project_root") else None,
        profile_path=str(profile_path) if profile_path else None,
        checklist_path=str(checklist_path) if checklist_path else None,
        offered_checklist_ids=[str(item.id) for item in checklist],
    )

    _render_review_checklist(ctx, checklist, _selected_review_axes(ctx, checklist, review_profile))
    ctx.textual.end_step("success")
    return Success("Review checklist built", metadata={"review_checklist": checklist})


# No declare_ai_usage: this step makes no AI call, so it must not appear in the AI
# Configuration screen as something a model can be assigned to.
def build_review_plan(ctx: WorkflowContext) -> WorkflowResult:
    """
    Decide how much attention every changed file gets, and what the deep session reads.
    No AI call.

    One rule per file (`resolve_file_attention`): deep files are read by the deep
    session, glance files go to the triage, skipped files are named on screen. The deep
    tier IS the selection -- there is no scorer ranking files for a cut and no model
    choosing again.

    This replaced three steps. An AI planning call (run `4fd7f345`: 92,463 input tokens to
    choose 7 of the 9 files the tiers had already marked deep, leaving two unreviewed), a
    scorer ranking files for a 12-file ceiling that no longer exists, and a PR size
    classification nothing consumed.

    Requires (from ctx.data):
        change_manifest (ChangeManifest)
        review_checklist (List[ReviewChecklistItem])

    Outputs (saved to ctx.data):
        attention_plan (AttentionPlan)
        review_budget (ReviewBudget)
        review_plan, validated_review_plan (ReviewPlan)

    Returns:
        Success, Exit when nothing is reviewable, or Error
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Review Plan")

    manifest = ctx.get("change_manifest")
    checklist = ctx.get("review_checklist", [])
    review_profile = _get_review_profile(ctx)
    if not manifest:
        ctx.textual.error_text("No change manifest in context")
        ctx.textual.end_step("error")
        return Error("No change manifest in context")

    from ..operations.attention_operations import (
        resolve_file_attention,
        summarize_attention_plan,
    )
    from ..operations.review_strategy_operations import build_deterministic_review_plan

    attention_plan = resolve_file_attention(manifest.files, review_profile)
    logger.debug("attention_plan_resolved", **summarize_attention_plan(attention_plan))
    _render_attention_plan(ctx, attention_plan)

    budget = review_budget()
    logger.debug(
        "review_budget_resolved",
        deep_max_prompt_chars=budget.deep_max_prompt_chars,
        triage_max_prompt_chars=budget.triage_max_prompt_chars,
        deep_timeout_base_seconds=budget.deep_timeout_base_seconds,
        deep_timeout_per_file_seconds=budget.deep_timeout_per_file_seconds,
        deep_timeout_max_seconds=budget.deep_timeout_max_seconds,
    )

    metadata = {"attention_plan": attention_plan, "review_budget": budget}
    if attention_plan.reviewable_count == 0:
        ctx.textual.dim_text("Nothing reviewable in this PR.")
        ctx.textual.end_step("skip")
        return Exit("Nothing reviewable in this PR", metadata=metadata)

    plan = build_deterministic_review_plan(attention_plan, checklist, review_profile)
    logger.info(
        "review_plan_built",
        focus_files=len(plan.focus_files),
        review_axes=len(plan.review_axes),
        attention_counts=attention_plan.counts,
    )
    ctx.textual.end_step("success")
    return Success(
        "Review plan built",
        metadata={**metadata, "review_plan": plan, "validated_review_plan": plan},
    )


def _get_review_budget(ctx: WorkflowContext) -> ReviewBudget:
    """The budget for this review, or Titan's constants when the step runs standalone.

    Falling back rather than failing: the budget carries no decision a user made, so a
    step invoked outside the full workflow should run with the shipped numbers instead
    of erroring on missing context.
    """
    return ctx.get("review_budget") or review_budget()


def _get_review_profile(ctx: WorkflowContext) -> ReviewProfile:
    """Resolve review profile from workflow managers with cached fallback."""
    review_profile = ctx.get("review_profile")
    if review_profile:
        return review_profile
    if ctx.github_managers:
        return ctx.github_managers.review_profile.get_effective_profile()
    from ..review_profiles import DEFAULT_REVIEW_PROFILE

    return DEFAULT_REVIEW_PROFILE.model_copy(deep=True)


def _render_attention_plan(ctx: WorkflowContext, plan) -> None:
    """Show how the PR splits by attention, grouped by tier and by why.

    The counts line comes first, and "not reviewed" is always on it: a review that
    looked at 12 of 108 files used to print a green tick and nothing else. Files sit
    behind one collapsed row per group, so the step reads as the shape of the PR
    instead of a wall of paths; the tier rows are open so the groups show at once.
    """
    from titan_cli.ui.tui.widgets import CollapsibleEntry
    from titan_cli.ui.tui.widgets.collapsible_list import escape_markup

    from ..models.review_enums import AttentionTier
    from ..operations.attention_operations import group_attention_for_display, split_display_path

    counts = plan.counts
    ctx.textual.dim_text(
        f"{counts[AttentionTier.DEEP.value]} to read in full · "
        f"{counts[AttentionTier.GLANCE.value]} at a glance · "
        f"{counts[AttentionTier.SKIP.value]} not reviewed"
    )

    tier_titles = {
        AttentionTier.DEEP: "Read in full",
        AttentionTier.GLANCE: "At a glance",
        AttentionTier.SKIP: "Not reviewed",
    }
    groups = group_attention_for_display(plan)
    entries = []
    for tier in AttentionTier:
        children = []
        for group in (g for g in groups if g.tier == tier):
            body = []
            for path in group.paths:
                name, directory = split_display_path(path)
                body.append(f"{escape_markup(name)}  [dim]{escape_markup(directory)}[/dim]")
            children.append(
                CollapsibleEntry(title=escape_markup(group.label), right=str(len(group.paths)), body=body)
            )
        if children:
            entries.append(
                CollapsibleEntry(
                    title=tier_titles.get(tier, tier.value),
                    right=str(counts[tier.value]),
                    style="bold",
                    children=children,
                    expanded=True,
                )
            )
    ctx.textual.text(" ")
    ctx.textual.collapsible_list(entries)


def _render_review_config(ctx: WorkflowContext, profile_resolution, checklist_resolution) -> None:
    """Show where the review configuration came from, and what in it Titan ignored.

    What the merge replaced key by key, and how many rules of each kind are in force,
    go to the debug log rather than the screen: a reviewer cannot act on "replaced
    file_roles.tests", and the list ran to a dozen lines on a project that overrides
    everything. What stays visible is what signals a broken project file -- a `remove:`
    target that matched nothing, and keys Titan does not read -- folded into one line per
    file so a stale file does not bury the step.
    """
    from ..operations.review_config_merge_operations import summarize_ignored_keys

    ctx.textual.dim_text(
        f"Review config · profile: {profile_resolution.source} · "
        f"checklist: {checklist_resolution.source}"
    )
    for label, resolution in (("profile", profile_resolution), ("checklist", checklist_resolution)):
        report = resolution.report
        for target in report.unknown_removals:
            ctx.textual.warning_text(
                f"  {label}: 'remove: {target}' matched nothing — check the spelling"
            )
        ignored = summarize_ignored_keys(getattr(report, "ignored_keys", []) or [])
        if ignored:
            # Unknown covers both a typo and a key Titan no longer reads (the scoring
            # keys an older profile still carries), so the message names both.
            ctx.textual.warning_text(
                f"  {label}: ignored, not settings Titan reads (misspelled or removed): "
                + "; ".join(ignored)
            )


def _selected_review_axes(ctx: WorkflowContext, checklist: list, review_profile: ReviewProfile) -> set | None:
    """The axes the deep session will be asked about, or None without a manifest.

    Resolved with the same two functions Review Plan uses, so what is bold here is what
    that step sends. Computed here because this is where the categories are listed; the
    list alone does not tell a reviewer which of them this PR triggers.
    """
    manifest = ctx.get("change_manifest")
    if not manifest:
        return None
    from ..models.review_enums import AttentionTier
    from ..operations.attention_operations import resolve_file_attention
    from ..operations.review_profile_operations import select_review_axes

    attention_plan = resolve_file_attention(manifest.files, review_profile)
    deep_paths = attention_plan.paths_for(AttentionTier.DEEP)
    return set(select_review_axes(checklist, deep_paths, review_profile))


def _render_review_checklist(ctx: WorkflowContext, checklist: list, selected: set | None) -> None:
    """Render the categories this project offers, the ones this PR applies in bold."""
    if selected is None:
        ctx.textual.success_text(f"✓ {len(checklist)} checklist categories offered")
    else:
        applied = sum(1 for item in checklist if item.id in selected)
        ctx.textual.success_text(
            f"✓ {len(checklist)} checklist categories offered · {applied} apply to this PR"
        )
    ctx.textual.text(" ")
    for item in checklist:
        # Show the human-readable name, not the snake_case category id.
        name = item.name or str(item.id)
        if selected is not None and item.id in selected:
            ctx.textual.bold_text(name)
        else:
            ctx.textual.dim_text(name)


def _show_review_context_batches(ctx: WorkflowContext, batches: list) -> None:
    """Show what each deep session receives, grouped by HOW it receives each file.

    A flat list of every path repeated what Review Plan had just shown and hid the only
    thing this step adds: which files arrive with their diff, which lost their added
    lines to the prompt budget, and which are only named for a triage question.
    """
    from titan_cli.ui.tui.widgets import CollapsibleEntry
    from titan_cli.ui.tui.widgets.collapsible_list import escape_markup

    from ..operations.attention_operations import split_display_path
    from ..operations.context_resolution_operations import (
        CONTEXT_GROUP_LABELS,
        group_batch_files_by_delivery,
    )

    for batch in batches:
        groups = group_batch_files_by_delivery(batch)
        children = []
        for key, paths in groups.items():
            body = []
            for path in paths:
                name, directory = split_display_path(path)
                body.append(f"{escape_markup(name)}  [dim]{escape_markup(directory)}[/dim]")
            children.append(
                CollapsibleEntry(title=CONTEXT_GROUP_LABELS[key], right=str(len(paths)), body=body)
            )
        related_count = len(getattr(batch, "related_files", {}) or {})
        if related_count:
            # Named, not included: the session opens them in the worktree if it needs them.
            children.append(
                CollapsibleEntry(title="Related files pointed out", right=str(related_count))
            )
        ctx.textual.text(" ")
        ctx.textual.collapsible_list([
            CollapsibleEntry(
                title=f"Deep session · {len(batch.files_context)} file(s)",
                # Kept: the findings step names the same id, so the two can be matched.
                right=batch.batch_id,
                style="bold",
                children=children,
                expanded=True,
            )
        ])
        if getattr(batch, "degraded_context", False):
            ctx.textual.dim_text("  context reduced to fit the AI prompt size limit")


def _render_findings_batch_started(ctx: WorkflowContext, batch) -> None:
    """Render the start of a findings batch review: a count, the files behind a fold.

    Review Plan already listed every deep file, grouped; repeating 18 full paths here
    pushed the part of this step that is new -- the result -- off the screen.
    """
    from titan_cli.ui.tui.widgets import CollapsibleEntry
    from titan_cli.ui.tui.widgets.collapsible_list import escape_markup

    from ..operations.attention_operations import split_display_path

    file_paths = list(getattr(batch, "files_context", {}).keys())
    body = []
    for path in file_paths:
        name, directory = split_display_path(path)
        body.append(f"{escape_markup(name)}  [dim]{escape_markup(directory)}[/dim]")
    ctx.textual.text(" ")
    ctx.textual.collapsible_list([
        CollapsibleEntry(
            title=f"Reading {len(file_paths)} file(s) in full",
            right=batch.batch_id,
            style="bold",
            body=body,
        )
    ])


def _retry_findings_batch_reformat(
    adapter, previous_stdout: str, cwd: Optional[str], batch_id: str, structured: bool, effort: Optional[str] = None
):
    """Ask the same CLI to reformat its own previous output as a JSON array, without
    rerunning the full analysis, using a short timeout distinct from the main one."""
    from ..operations.findings_operations import FINDINGS_DISALLOWED_TOOLS, findings_json_schema, parse_findings_response

    reformat_prompt = build_json_reformat_prompt(previous_stdout, kind="array")
    schema = findings_json_schema() if structured else None
    disallowed_tools = list(FINDINGS_DISALLOWED_TOOLS) if adapter.supports_tool_restriction else None
    _log_ai_prompt("ai_review_findings_reformat_retry", adapter.cli_name.value, reformat_prompt, batch_id=batch_id)
    response = run_interruptible(
        lambda: adapter.execute(
            reformat_prompt,
            cwd=cwd,
            timeout=REFORMAT_RETRY_TIMEOUT_SECONDS,
            json_schema=schema,
            disallowed_tools=disallowed_tools,
            effort=effort if adapter.supports_effort_control else None,
        )
    )
    _log_ai_response(
        step_name="ai_review_findings_reformat_retry",
        cli_name=adapter.cli_name.value,
        stdout=response.stdout,
        stderr=response.stderr,
        exit_code=response.exit_code,
        batch_id=batch_id,
    )
    if not response.succeeded:
        return ClientError(
            error_message=f"Reformat retry CLI call failed: {_cli_failure_reason(response, adapter.cli_name.value)}",
            error_code="REFORMAT_RETRY_FAILED",
            log_level="warning",
        )
    return parse_findings_response(response.stdout, structured=structured)


def _render_findings_batch_split(ctx: WorkflowContext, batch_id: str, produced_batches: list[str]) -> None:
    """Render a batch split caused by prompt budget constraints."""
    ctx.textual.dim_text(
        f"{batch_id} was too large for one AI call — split into {', '.join(produced_batches)}"
    )


def _render_findings_batch_degraded(ctx: WorkflowContext, batch_id: str) -> None:
    """Render an in-place context reduction (no new batches) caused by prompt budget constraints."""
    ctx.textual.dim_text(f"{batch_id} was too large — file context reduced to fit the AI call")


def _retry_timed_out_worktree_batch(ctx: WorkflowContext, batch, run, budget) -> list[tuple]:
    """Retry a timed-out worktree_reference batch in bounded hunks_only mode.

    Runs on the step thread (UI access is fine). Returns the (batch, outcome) pairs the
    retry produced -- more than one when the fallback had to be split -- or an empty list
    when no bounded fallback was possible at all, in which case the caller keeps the
    original failed outcome.

    A fallback that does not fit the budget is SPLIT through the same
    `fit_batch_to_budget` machinery phase 1 uses, not abandoned. It used to return early
    and keep the timeout silently, with no UI line and no log event: measured on PR #254,
    one file's fallback prompt came to 149,353 chars against an 18,000 budget and that
    file went unreviewed in three consecutive runs without saying so. Every outcome here
    is logged, including the one where nothing can be retried.

    File reads are forbidden in the fallback (`allow_file_reads=False`): degrading back
    to a worktree_reference is exactly the mode that just timed out.
    """
    from ..operations.findings_operations import (
        build_findings_prompt_parts,
        build_timeout_fallback_batch,
    )

    budget = budget or review_budget()
    budget_chars = budget.deep_max_prompt_chars

    fallback = build_timeout_fallback_batch(
        batch, ctx.get("review_diff", ""), diff_manager=ctx.get("review_diff_manager")
    )
    if not fallback:
        logger.warning(
            "findings_batch_timeout_fallback_unavailable",
            batch_id=batch.batch_id,
            reason="no_diff_hunks",
            paths=sorted(batch.files_context),
        )
        ctx.textual.warning_text(
            f"⚠ {batch.batch_id} timed out and has no diff hunks to retry with. "
            f"NOT reviewed: {', '.join(sorted(batch.files_context)) or 'unknown files'}"
        )
        return []

    manager = get_prompt_budget_manager()
    queue = [fallback]
    ready: list[tuple] = []
    oversized: list = []
    while queue:
        candidate = queue.pop(0)
        prompt_parts = build_findings_prompt_parts(candidate)
        fitted_batches, changed = manager.fit_batch_to_budget(
            candidate, prompt_parts, budget_chars, allow_file_reads=False
        )
        if changed:
            queue = fitted_batches + queue
            continue
        fitted = fitted_batches[0]
        prompt = build_findings_prompt_parts(fitted)["prompt"]
        if len(prompt) > budget_chars:
            oversized.append(fitted)
            continue
        ready.append((fitted, prompt))

    if oversized:
        # Reached only when a single hunk on its own exceeds the budget, so there is
        # nothing left to divide. Said out loud rather than dropped.
        logger.warning(
            "findings_batch_timeout_fallback_oversized",
            batch_id=batch.batch_id,
            oversized_batches=[candidate.batch_id for candidate in oversized],
            prompt_budget_target_chars=budget_chars,
        )
        skipped = sorted({path for candidate in oversized for path in candidate.files_context})
        ctx.textual.warning_text(
            f"⚠ {batch.batch_id} timed out and part of its fallback is too large to send. "
            f"NOT reviewed: {', '.join(skipped) or 'unknown files'}"
        )

    if not ready:
        return []

    if len(ready) == 1:
        ctx.textual.dim_text(
            f"{batch.batch_id} timed out exploring the worktree — retrying with inline diff hunks only"
        )
    else:
        ctx.textual.dim_text(
            f"{batch.batch_id} timed out exploring the worktree — retrying with inline diff "
            f"hunks only, split into {len(ready)} call(s)"
        )
    logger.info(
        "findings_batch_timeout_fallback",
        batch_id=batch.batch_id,
        fallback_batch_ids=[fallback_batch.batch_id for fallback_batch, _ in ready],
        prompt_actual_chars=[len(prompt) for _, prompt in ready],
        prompt_budget_target_chars=budget_chars,
        oversized=len(oversized),
    )

    results: list[tuple] = []
    for index, (fallback_batch, prompt) in enumerate(ready, start=1):
        label = fallback_batch.batch_id
        if len(ready) > 1:
            label += f" ({index}/{len(ready)})"
        with ctx.textual.loading(f"Retrying {label} with inline hunks…"):
            results.append((fallback_batch, run((fallback_batch, prompt, None))))
    return results


def _render_settled_questions(ctx: WorkflowContext, batches, dismissed: list, findings: list) -> None:
    """Say what became of every question the first pass raised.

    Three outcomes, and the third is the one worth showing: confirmed (a finding names
    that file), dismissed (the session says what it checked), or UNANSWERED — which used
    to look exactly like a dismissal, because both produce nothing.
    """
    asked = {
        (item.get("path") or "").strip()
        for batch in batches
        for item in (batch.triage_suspicions or [])
    }
    asked.discard("")
    if not asked:
        return

    from ..operations.findings_operations import normalize_finding_path

    finding_paths = {
        normalize_finding_path(finding.get("path") or "")
        for finding in findings or []
        if isinstance(finding, dict)
    }
    confirmed = {path for path in asked if normalize_finding_path(path) in finding_paths}
    # One outcome per question. A session can report a finding on a file AND dismiss its
    # question in the same answer; the finding is what reaches the PR, so it wins.
    dismissed = [item for item in dismissed if item["path"] not in confirmed]
    dismissed_paths = {item["path"] for item in dismissed}
    unanswered = sorted(asked - confirmed - dismissed_paths)

    logger.info(
        "triage_suspicion_outcomes",
        asked=len(asked),
        confirmed=len(confirmed),
        dismissed=len(dismissed_paths),
        unanswered=len(unanswered),
        unanswered_paths=unanswered,
    )
    from titan_cli.ui.tui.widgets.collapsible_list import escape_markup

    ctx.textual.text(" ")
    ctx.textual.bold_text(
        f"Triage questions · {len(confirmed)} confirmed · {len(dismissed_paths)} dismissed"
        + (f" · {len(unanswered)} unanswered" if unanswered else "")
    )
    for path in sorted(confirmed):
        ctx.textual.text(" ")
        ctx.textual.text(_display_file_label(path))
        ctx.textual.success_text("  ↳ confirmed — reported as a finding")
    for item in dismissed:
        ctx.textual.text(" ")
        ctx.textual.text(_display_file_label(item["path"]))
        reason = _highlight_inline_code(escape_markup(item.get("reason", "") or "no reason given"))
        ctx.textual.text(f"  ↳ [dim]dismissed:[/dim] {reason}")
    for path in unanswered:
        ctx.textual.text(" ")
        ctx.textual.text(_display_file_label(path))
        ctx.textual.warning_text("  ↳ unanswered — the session did not settle this one")


def _display_file_label(path: str) -> str:
    """`Name.kt  app/…/dir` as markup: the name bold, where it lives dimmed."""
    from titan_cli.ui.tui.widgets.collapsible_list import escape_markup

    from ..operations.attention_operations import split_display_path

    name, directory = split_display_path(path)
    label = f"[bold]{escape_markup(name)}[/bold]"
    return f"{label}  [dim]{escape_markup(directory)}[/dim]" if directory else label


def _render_out_of_scope_findings(ctx: WorkflowContext, rejected: list[dict]) -> None:
    """Name every finding dropped for its path, not only how many.

    Shown, not just logged: a model naming files it was never given is a signal about
    the prompt -- and a finding about a real file outside the PR may be exactly the
    regression the PR causes, so the reviewer has to be able to see it was dropped.
    """
    from titan_cli.ui.tui.widgets.collapsible_list import escape_markup

    ctx.textual.text(" ")
    ctx.textual.warning_text(f"Discarded {len(rejected)} finding(s) about files the review was not given:")
    for item in rejected:
        where = "not in this PR" if item.get("reason") == "unknown_path" else "not in this batch"
        ctx.textual.text(
            f"  {_display_file_label(item.get('path', ''))} [dim]· {where}[/dim]"
        )
        if item.get("title"):
            ctx.textual.text(f"  ↳ {_highlight_inline_code(escape_markup(item['title']))}")


def _render_findings_batch_result(
    ctx: WorkflowContext,
    batch_id: str,
    *,
    status: str,
    findings_count: int = 0,
    detail: str = "",
) -> None:
    """Render the outcome of a findings batch review."""
    if status == "success":
        ctx.textual.success_text(f"✓ {batch_id} complete · {findings_count} raw finding(s)")
        return

    message = f"{batch_id} {status}"
    if detail:
        message += f" · {detail}"
    ctx.textual.warning_text(message)


def _attach_content_provider(diff_manager, root: Optional[str]) -> None:
    """
    Give the diff manager a way to read whole files from ``root``.

    Only call this with a root already verified to hold the PR's head revision — the
    provider is trusted to return the code the diff describes.
    """
    if diff_manager is None or not root:
        return

    from ..operations.context_resolution_operations import read_file_content

    diff_manager.attach_content_provider(lambda path: read_file_content(path, root))


def _resolve_file_read_access(ctx: WorkflowContext, worktree_path: Optional[str]):
    """
    Decide whether files on disk may be used as this PR's code.

    Worktree creation is allowed to fail in the workflow, and the fallback root is the
    user's own checkout — which is usually on a different branch. Query its HEAD and
    dirty state so the decision is made on facts rather than assumed.
    """
    from ..operations.context_resolution_operations import resolve_file_read_access

    if worktree_path:
        return resolve_file_read_access(worktree_path)

    head_sha = ctx.data.get("review_commit_sha")
    checkout_sha = None
    checkout_dirty = None

    if ctx.git:
        match ctx.git.get_current_commit():
            case ClientSuccess(data=sha):
                checkout_sha = (sha or "").strip()
            case ClientError(error_message=err):
                logger.debug("checkout_sha_unavailable", error=err)

        match ctx.git.has_uncommitted_changes():
            case ClientSuccess(data=dirty):
                checkout_dirty = dirty
            case ClientError(error_message=err):
                logger.debug("checkout_dirty_state_unavailable", error=err)

    access = resolve_file_read_access(
        worktree_path=None,
        head_sha=head_sha,
        checkout_sha=checkout_sha,
        checkout_dirty=checkout_dirty,
    )
    logger.debug(
        "file_read_access_resolved",
        allowed=access.allowed,
        source=access.source,
        reason=access.reason,
    )
    return access


def resolve_review_context(ctx: WorkflowContext) -> WorkflowResult:
    """
    Fetch the exact code context according to the validated review plan.

    For each file in the plan, extracts code using the chosen read_mode:
    - hunks_only: diff hunks as-is (already has 20 lines of context)
    - expanded_hunks: hunks + extra surrounding lines from the actual file
    - full_file: reads the complete file from disk

    Also resolves any extra context requests (related_tests, related_context).

    Requires (from ctx.data):
        validated_review_plan (ReviewPlan)
        change_manifest (ChangeManifest)
        review_diff (str)
        existing_comments_index (List[ExistingCommentIndexEntry])
        review_checklist (List[ReviewChecklistItem])

    Outputs (saved to ctx.data):
        review_context_package (ReviewContextPackage)

    Returns:
        Success or Error
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Resolve Review Context")

    plan = ctx.get("validated_review_plan")
    manifest = ctx.get("change_manifest")
    diff = ctx.get("review_diff", "")
    comment_context = ctx.get("comment_review_context", [])
    checklist = ctx.get("review_checklist", [])
    budget = _get_review_budget(ctx)
    review_profile = _get_review_profile(ctx)
    worktree_path = ctx.data.get("worktree_path")
    project_root = worktree_path or ctx.data.get("project_root")

    if not plan or not manifest:
        ctx.textual.error_text("Missing validated_review_plan or change_manifest in context")
        ctx.textual.end_step("error")
        return Error("Missing validated_review_plan or change_manifest in context")

    if not diff:
        ctx.textual.error_text("No diff in context (run fetch_pr_review_bundle first)")
        ctx.textual.end_step("error")
        return Error("No diff in context (run fetch_pr_review_bundle first)")

    from ..operations.context_resolution_operations import build_review_context_package
    diff_manager = ctx.get("review_diff_manager")

    read_access = _resolve_file_read_access(ctx, worktree_path)
    if read_access.allowed:
        ctx.textual.dim_text(f"Reading files from {read_access.source} ({read_access.reason})")
        # Same verified root powers the comment-rendering path, so a finding about
        # pre-existing code can show that code instead of nothing.
        _attach_content_provider(diff_manager, project_root)
    else:
        ctx.textual.warning_text(
            f"Reviewing from the diff only — {read_access.reason}. "
            "Full-file and expanded-hunk context are disabled to avoid mixing revisions."
        )

    try:
        with ctx.textual.loading("Extracting code context…"):
            package = build_review_context_package(
                plan=plan,
                diff=diff,
                manifest=manifest,
                checklist=checklist,
                comment_context=comment_context,
                budget=budget,
                cwd=project_root,
                diff_manager=diff_manager,
                allow_file_reads=read_access.allowed,
                # The whole change's shape, so the session judges the PR rather than the
                # files it happens to have been handed. Absent only if build_review_plan did
                # not run, in which case the batches simply carry no shape section.
                attention_plan=ctx.get("attention_plan"),
                review_profile=review_profile,
                # The first pass's questions ride in the SAME session that reviews the
                # core, because that is who can answer them best (D-014).
                triage_suspicions=ctx.get("review_triage_suspicions", []),
            )
    except Exception as e:
        ctx.textual.error_text(f"Failed to resolve review context: {e}")
        ctx.textual.end_step("error")
        return Error(f"Failed to resolve review context: {e}")

    ctx.data["review_context_package"] = package
    ctx.data["review_context_batches"] = package.batches
    ctx.data["review_file_reads_allowed"] = read_access.allowed

    batch_count = len(package.batches)
    files_count = sum(len(batch.files_context) for batch in package.batches)

    ctx.textual.success_text(
        f"✓ Context ready · {files_count} file(s)"
        + (f" in {batch_count} sessions" if batch_count > 1 else "")
    )
    # Shown, because a review's judgement depends on which project rules it was told to
    # read, and "no project context" is the thing worth noticing when a finding argues
    # against a convention this repo chose on purpose.
    context_docs = package.batches[0].context_docs if package.batches else []
    if context_docs:
        ctx.textual.dim_text(f"Project rules read first: {', '.join(context_docs)}")
    else:
        ctx.textual.dim_text(
            "no project context documents found — the review judges the diff against "
            "general practice only (set context_docs in .titan/review/profile.yaml)"
        )
    logger.info(
        "review_context_summary",
        comments_in_context=sum(len(batch.comment_context) for batch in package.batches),
        context_docs=len(context_docs),
    )
    _show_review_context_batches(ctx, package.batches)
    ctx.textual.end_step("success")
    return Success(
        "Review context resolved",
        metadata={
            "review_context_package": package,
            "review_context_batches": package.batches,
            "review_file_reads_allowed": read_access.allowed,
        },
    )


# ============================================================================
# PHASE 4: TARGETED REVIEW (Second AI Call)
# ============================================================================


def _scoped_batch_outcome(
    batch, raw: list, manifest_paths: Optional[set], project_root: Optional[str] = None
) -> dict:
    """Drop findings about files this batch never showed the model.

    The anchoring layer can resolve a line in ANY file of the PR, so a finding whose
    path the batch did not send still anchors and publishes — on a file the model never
    read. With one or two files per batch a wrong path is unlikely; a packed batch of
    ten or fifteen makes misattribution an ordinary mistake, which is why this runs
    before the findings leave the worker.

    Deliberately NOT a downgrade-and-keep: an unverifiable claim with its line stripped
    still reads as a review finding, and the reviewer cannot tell it apart from one the
    model actually looked at. Every drop is logged with its reason so the rate is
    measurable, and if it ever turns out to cost real signal the log is the evidence.
    """
    from ..operations.findings_operations import (
        batch_scope_paths,
        partition_findings_by_batch_scope,
    )

    kept, rejected = partition_findings_by_batch_scope(
        raw,
        batch_scope_paths(batch),
        manifest_paths or set(),
        is_repo_file=_repo_file_checker(project_root),
    )
    outside_pr = sorted(
        {
            finding.get("path")
            for finding in kept
            if isinstance(finding, dict)
            and finding.get("path")
            and finding.get("path") not in (manifest_paths or set())
            and finding.get("path") not in batch_scope_paths(batch)
        }
    )
    if outside_pr:
        logger.info("findings_outside_pr_kept", batch_id=batch.batch_id, paths=outside_pr)
    if rejected:
        logger.warning(
            "findings_outside_batch_scope",
            batch_id=batch.batch_id,
            batch_paths=sorted(batch.files_context),
            dropped=len(rejected),
            kept=len(kept),
            rejected=rejected,
        )
    return {
        "status": "success",
        "raw": kept,
        "detail": "",
        "out_of_scope": len(rejected),
        "out_of_scope_findings": rejected,
    }


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


def _log_parsed_findings(batch_id: str, raw: list, dismissed: list[dict]) -> None:
    """Record what the session answered, whole, before anything filters it.

    The response log keeps only the edges of stdout, and the finding that decides a
    comparison between two runs is as likely to sit in the middle as anywhere. The
    parsed answer is a fraction of the envelope, so it is kept in full: a run must be
    auditable from its own log.
    """
    logger.debug(
        "findings_batch_parsed",
        batch_id=batch_id,
        findings_count=len(raw),
        findings=raw,
        dismissed=dismissed,
    )


def _settled_questions(stdout: str, batch) -> list[dict]:
    """The questions this batch dismissed, scoped to the ones it was actually asked.

    Recorded because a question opened and dismissed on purpose is otherwise
    indistinguishable from one ignored: both produce no finding.
    """
    from ..operations.findings_operations import parse_dismissals

    if not batch.triage_suspicions:
        return []
    asked = {(item.get("path") or "").strip() for item in batch.triage_suspicions}
    return parse_dismissals(stdout, {path for path in asked if path})


def _execute_findings_batch(
    adapter,
    batch,
    prompt: str,
    *,
    project_root: Optional[str],
    findings_schema: Optional[dict],
    disallowed_tools: Optional[list],
    effort: Optional[str],
    use_structured_output: bool,
    strategy_name: Optional[str],
    timeout_seconds: int,
    manifest_paths: Optional[set] = None,
) -> dict:
    """Run one findings batch end-to-end: CLI call, parse, reformat retry, scope check.

    Runs inside a worker thread when batches execute concurrently, so it must not
    touch `ctx`/the UI — it returns an outcome dict the step thread renders:
    {"status": "success" | "failed", "raw": list | None, "detail": str}, plus
    "out_of_scope" for findings the batch was not entitled to make.

    `manifest_paths` is every path in the PR, used only to tell a hallucinated path
    apart from a real file this batch was simply not shown.

    `timeout_seconds` is derived from the batch's file count by the caller and logged
    with the call, so the constants behind it can be corrected from real runs.
    """
    from ..operations.findings_operations import parse_findings_response

    adapter_started_at = time.monotonic()
    # run_interruptible here also covers the pooled path: on app exit each worker
    # raises WorkflowAborted, its future completes, and the step thread's
    # future.result() re-raises it instead of blocking on a live CLI call.
    response = run_interruptible(
        lambda: adapter.execute(
            prompt,
            cwd=project_root,
            timeout=timeout_seconds,
            json_schema=findings_schema,
            disallowed_tools=disallowed_tools,
            effort=effort,
        )
    )
    adapter_duration_seconds = time.monotonic() - adapter_started_at
    worktree_reference_count = sum(
        1 for entry in batch.files_context.values() if entry.worktree_reference
    )
    logger.info(
        "findings_batch_adapter_call",
        batch_id=batch.batch_id,
        cli=adapter.cli_name.value,
        files_context=len(batch.files_context),
        worktree_reference_count=worktree_reference_count,
        prompt_actual_chars=len(prompt),
        duration_seconds=round(adapter_duration_seconds, 3),
        timeout_seconds=timeout_seconds,
        exit_code=response.exit_code,
        timed_out=response.exit_code == 124,
        quota_exhausted=response.quota_exhausted,
        structured_output=use_structured_output,
        effort=effort,
    )
    _log_ai_response(
        step_name="ai_review_findings",
        cli_name=adapter.cli_name.value,
        stdout=response.stdout,
        stderr=response.stderr,
        exit_code=response.exit_code,
        batch_id=batch.batch_id,
        files_context=len(batch.files_context),
        related_files=len(batch.related_files),
        checklist_items=len(batch.checklist_applicable),
        comment_entries=len(batch.comment_context),
        strategy=strategy_name,
    )

    if not response.succeeded:
        reason = _cli_failure_reason(response, adapter.cli_name.value)
        logger.debug(
            "findings_batch_failed",
            batch_id=batch.batch_id,
            exit_code=response.exit_code,
            quota_exhausted=response.quota_exhausted,
            reason=reason,
        )
        return {
            "status": "failed",
            "raw": None,
            "detail": reason,
            "timed_out": response.exit_code == 124,
        }

    match parse_findings_response(response.stdout, structured=use_structured_output):
        case ClientSuccess(data=raw) if isinstance(raw, list):
            dismissed = _settled_questions(response.stdout, batch)
            _log_parsed_findings(batch.batch_id, raw, dismissed)
            return {
                **_scoped_batch_outcome(batch, raw, manifest_paths, project_root),
                "dismissed": dismissed,
            }
        case ClientSuccess(data=raw):
            # A structured success whose payload isn't a findings list (e.g. a dict)
            # must not vanish silently — treat it like any other parse failure.
            parse_error = f"non-list findings payload ({type(raw).__name__})"
        case ClientError(error_message=err):
            parse_error = err

    logger.debug("findings_batch_parse_failed", batch_id=batch.batch_id, error=parse_error)
    match _retry_findings_batch_reformat(
        adapter, response.stdout, project_root, batch.batch_id, use_structured_output, effort
    ):
        case ClientSuccess(data=raw) if isinstance(raw, list):
            logger.debug(
                "findings_batch_reformat_recovered",
                batch_id=batch.batch_id,
                findings_count=len(raw),
            )
            _log_parsed_findings(batch.batch_id, raw, [])
            return _scoped_batch_outcome(batch, raw, manifest_paths, project_root)
        case _:
            logger.debug("findings_batch_reformat_failed", batch_id=batch.batch_id)
            return {"status": "failed", "raw": None, "detail": "parse error"}


@declare_ai_usage(
    task=AITask.CODE_REVIEW_TRIAGE,
    executes=[AIProviderType.CLI_HEADLESS],
    enforces=True,
)
def ai_review_triage(ctx: WorkflowContext) -> WorkflowResult:
    """
    Call 1 of the review: triage every file the deep session will not open.

    Diffs only, no repo access, on whatever model the user assigned to
    `code_review_triage` -- a cheap one is the point. It **publishes nothing**: the notes
    and suspicions it returns are working material for `ai_review_findings`, which opens
    the file and confirms or drops each one.

    Best-effort by construction. A triage that fails leaves those files exactly where they
    were before this step existed -- unlooked-at -- so it never fails the review.

    Requires (from ctx.data):
        review_diff (str)
        attention_plan (AttentionPlan)
        validated_review_plan (ReviewPlan)

    Outputs (saved to ctx.data):
        review_triage_notes (list[dict]): one note per triaged file
        review_triage_suspicions (list[dict]): the subset worth opening

    Returns:
        Success (always, when it can run at all)
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Triage")

    from ..models.review_enums import AttentionTier
    from ..operations.findings_operations import FINDINGS_DISALLOWED_TOOLS
    from ..operations.triage_operations import (
        build_triage_batches,
        build_triage_prompt_parts,
        parse_triage_notes,
        triage_json_schema,
        suspicions_from_notes,
    )

    diff = ctx.get("review_diff", "")
    attention_plan = ctx.get("attention_plan")
    plan = ctx.get("validated_review_plan") or ctx.get("review_plan")
    budget = _get_review_budget(ctx)
    manifest = ctx.get("change_manifest")
    project_root = ctx.data.get("project_root")

    if not diff or not attention_plan:
        ctx.textual.dim_text("Nothing to triage (no diff or no attention plan)")
        ctx.textual.end_step("success")
        return Success("Triage skipped", metadata={"review_triage_notes": [], "review_triage_suspicions": []})

    # Everything the deep session will NOT open: the glance tier, plus any deep file that
    # fell outside the session budget. Deep files it IS opening are excluded because
    # their diffs travel in the deep prompt already -- triaging them would pay twice for
    # the same orientation.
    deep_read = {file_plan.path for file_plan in (plan.focus_files if plan else [])}
    to_triage = [
        entry.path
        for entry in attention_plan.files
        if entry.tier != AttentionTier.SKIP and entry.path not in deep_read
    ]

    if not to_triage:
        ctx.textual.dim_text("Every reviewable file is in the deep session — nothing left to triage")
        ctx.textual.end_step("success")
        return Success("Triage not needed", metadata={"review_triage_notes": [], "review_triage_suspicions": []})

    batches = build_triage_batches(
        to_triage,
        diff,
        budget.triage_max_prompt_chars,
        diff_manager=ctx.get("review_diff_manager"),
        pr_manifest=manifest.pr if manifest else None,
    )
    if not batches:
        ctx.textual.dim_text(f"{len(to_triage)} file(s) have no diff hunks to triage")
        ctx.textual.end_step("success")
        return Success("Nothing triageable", metadata={"review_triage_notes": [], "review_triage_suspicions": []})

    adapter, route_note, ai_off = _resolve_review_adapter(ctx, ai_review_triage)
    if not adapter:
        # The files stay unlooked-at, which is where they were. Said out loud rather than
        # counted as covered.
        ctx.textual.warning_text(
            f"AI unavailable{f' ({route_note})' if route_note else ''} — "
            f"{len(to_triage)} file(s) NOT triaged"
        )
        ctx.textual.end_step("success")
        return Success("Triage unavailable", metadata={"review_triage_notes": [], "review_triage_suspicions": []})
    if route_note:
        ctx.textual.dim_text(route_note)
    _announce_review_adapter(ctx, adapter)

    use_structured_output = adapter.supports_structured_output
    schema = triage_json_schema() if use_structured_output else None
    disallowed = list(FINDINGS_DISALLOWED_TOOLS) if adapter.supports_tool_restriction else None

    # From the manifest, not from the deep batches: the triage runs BEFORE the deep
    # context exists, so reading it from there handed the triage no intent at all.
    from ..operations.prompt_formatting_operations import review_pr_description

    pr_intent = review_pr_description(manifest.pr.description) if manifest and manifest.pr else None

    notes: list[dict] = []
    ctx.textual.dim_text(
        f"Triaging {sum(len(b.files_context) for b in batches)} file(s) "
        f"in {len(batches)} call(s) with {adapter.cli_name.value.capitalize()}"
    )
    for batch in batches:
        parts = build_triage_prompt_parts(batch, pr_intent=pr_intent)
        prompt = parts["prompt"]
        _log_ai_prompt(
            step_name="ai_review_triage",
            cli_name=adapter.cli_name.value,
            prompt=prompt,
            batch_id=batch.batch_id,
            files_context=len(batch.files_context),
            prompt_budget_target_chars=budget.triage_max_prompt_chars,
            prompt_actual_chars=len(prompt),
        )
        started_at = time.monotonic()
        with ctx.textual.loading(f"Triaging {batch.batch_id} ({len(batch.files_context)} file(s))…"):
            response = run_interruptible(
                lambda: adapter.execute(
                    prompt,
                    cwd=project_root,
                    # Scaled by the files it notes: one call now carries the whole
                    # PR's glance tier, and its output grows with every file.
                    timeout=deep_call_timeout_seconds(budget, len(batch.files_context)),
                    json_schema=schema,
                    disallowed_tools=disallowed,
                )
            )
        duration = time.monotonic() - started_at
        logger.info(
            "triage_batch_adapter_call",
            batch_id=batch.batch_id,
            cli=adapter.cli_name.value,
            files_context=len(batch.files_context),
            prompt_actual_chars=len(prompt),
            duration_seconds=round(duration, 3),
            exit_code=response.exit_code,
            timed_out=response.exit_code == 124,
            structured_output=use_structured_output,
        )
        _log_ai_response(
            step_name="ai_review_triage",
            cli_name=adapter.cli_name.value,
            stdout=response.stdout,
            stderr=response.stderr,
            exit_code=response.exit_code,
            batch_id=batch.batch_id,
            files_context=len(batch.files_context),
        )
        if not response.succeeded:
            reason = _cli_failure_reason(response, adapter.cli_name.value)
            ctx.textual.warning_text(
                f"{batch.batch_id} not triaged · {reason} — "
                f"NOT looked at: {', '.join(sorted(batch.files_context))}"
            )
            continue
        batch_notes = parse_triage_notes(response.stdout, set(batch.files_context))
        notes.extend(batch_notes)
        flagged = len(suspicions_from_notes(batch_notes))
        ctx.textual.success_text(
            f"✓ {batch.batch_id} · {len(batch_notes)} note(s), {flagged} worth opening"
        )

    suspicions = suspicions_from_notes(notes)
    _render_triage_notes(ctx, notes, suspicions)
    logger.info(
        "triage_completed",
        triaged=len(to_triage),
        notes=len(notes),
        suspicions=len(suspicions),
        suspicion_paths=sorted({item["path"] for item in suspicions}),
    )
    # Whole, for the same reason as `findings_batch_parsed`: the questions the deep
    # session is handed are half of what explains its answer.
    logger.debug("triage_notes_parsed", notes=notes)
    ctx.textual.end_step("success")
    return Success(
        f"Triaged {len(notes)} file(s), {len(suspicions)} worth opening",
        metadata={"review_triage_notes": notes, "review_triage_suspicions": suspicions},
    )


def _render_triage_notes(ctx: WorkflowContext, notes: list[dict], suspicions: list[dict]) -> None:
    """Show what the triage flagged and WHY, one block per file, the quiet files named.

    The reason is the part a reviewer reads, so it gets a line of its own under the file
    name instead of trailing a full path on the same wrapped line; the path is shortened
    the way Review Plan shortens it, and inline `code` in the question is highlighted.
    """
    from titan_cli.ui.tui.widgets.collapsible_list import escape_markup

    from ..operations.attention_operations import split_display_path

    if not notes:
        return

    if suspicions:
        ctx.textual.text(" ")
        ctx.textual.bold_text(f"Worth opening · {len(suspicions)} of {len(notes)} file(s)")
        for item in suspicions:
            ctx.textual.text(" ")
            ctx.textual.text(_display_file_label(item["path"]))
            ctx.textual.text(f"  ↳ {_highlight_inline_code(escape_markup(item['suspicion']))}")

    quiet = [item for item in notes if not item.get("suspicion")]
    if quiet:
        ctx.textual.text(" ")
        names = ", ".join(escape_markup(split_display_path(item["path"])[0]) for item in quiet)
        ctx.textual.dim_text(f"Nothing stood out · {names}")


def _highlight_inline_code(text: str) -> str:
    """`code` spans from a model's prose -> bold, so identifiers stand out on screen."""
    return re.sub(r"`([^`\n]+)`", r"[bold]\1[/bold]", text)


@declare_ai_usage(
    task=AITask.CODE_REVIEW_FINDINGS,
    executes=[AIProviderType.CLI_HEADLESS],
    enforces=True,
)
def ai_review_findings(ctx: WorkflowContext) -> WorkflowResult:
    """Run the findings phase, and report its cost even if it is abandoned.

    The wrapper exists for the `finally`. This phase is where a review spends almost
    everything, and it is also the one a user interrupts when it is taking too long —
    which is precisely the moment they want to know what it cost. Emitting the summary
    only on the success path meant an aborted run reported nothing at all.

    `WorkflowAborted` is a `BaseException`, so `finally` is the only construct that
    still runs on an interrupt without catching it.

    Returns:
        Whatever the deep review returns: Success with raw findings, Skip when AI is
        off for the task, or Error when every batch failed.
    """
    try:
        return _ai_review_findings(ctx)
    finally:
        log_review_ai_cost(ctx, scope="findings_phase")


def _ai_review_findings(ctx: WorkflowContext) -> WorkflowResult:
    """
    Second AI call: find actionable problems in the exact code context.

    Sends the ReviewContextPackage (exact file content + applicable checklist +
    existing comments) to the selected headless CLI. The AI reviews only the
    code it was specifically directed to read in the planning phase.

    On parse failure or CLI error a batch is retried (reformat) and then marked
    failed. If every batch fails, the step returns Error — an empty result caused
    by total AI failure must not look like a clean review — while still publishing
    empty raw_findings so downstream steps run via the workflow's on_error: continue.

    Which CLI runs it comes from the `code_review_findings` task preference
    (AI Configuration screen), not from the workflow.

    Requires (from ctx.data):
        review_context_package (ReviewContextPackage)

    Outputs (saved to ctx.data):
        raw_findings (list | str): Raw AI output before normalization

    Returns:
        Success or Error
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Deep Review")

    batches = ctx.get("review_context_batches")
    budget = _get_review_budget(ctx)
    project_root = ctx.data.get("worktree_path") or ctx.data.get("project_root")

    if not batches:
        ctx.textual.error_text("No review_context_batches in context (run resolve_review_context first)")
        ctx.textual.end_step("error")
        return Error("No review_context_batches in context (run resolve_review_context first)")

    from ..operations.findings_operations import (
        FINDINGS_DISALLOWED_TOOLS,
        FINDINGS_WORKTREE_REFERENCE_EFFORT,
        build_default_findings,
        build_findings_prompt_parts,
        findings_json_schema,
        summarize_findings_prompt_parts,
    )

    adapter, route_note, ai_off = _resolve_review_adapter(ctx, ai_review_findings)

    if not adapter:
        reason = route_note or "No headless CLI available"
        ctx.data["raw_findings"] = build_default_findings()
        if ai_off:
            # The user turned AI off for this task: nothing failed — nothing was
            # meant to run. Downstream reads ai_findings_failed, and it must be
            # explicitly False here.
            ctx.textual.warning_text(f"{reason} — skipping AI findings")
            ctx.data["ai_findings_failed"] = False
            ctx.textual.end_step("success")
            return Success(
                "No findings (AI is off for this task)",
                metadata={"raw_findings": [], "ai_findings_failed": False},
            )
        # Routing failure (no CLI configured, not installed, wrong provider): the AI
        # never ran, so an empty result must not look like a clean review — same
        # contract as the all-batches-failed exit below. Empty findings are still
        # published so downstream steps run via on_error: continue.
        ctx.data["ai_findings_failed"] = True
        ctx.textual.error_text(
            f"{reason} — AI findings could not run. No code was reviewed."
        )
        ctx.textual.end_step("error")
        return Error(f"AI findings could not run: {reason}")

    _announce_review_adapter(ctx, adapter)

    # Structured output forces the CLI to return findings via a schema-validated tool
    # call instead of relying on the model to follow a "respond only with JSON" prompt
    # instruction, which models frequently ignore in favor of a prose summary.
    use_structured_output = adapter.supports_structured_output
    findings_schema = findings_json_schema() if use_structured_output else None
    # Removes Bash (and other unneeded tools) from the CLI's own session so it can't explore
    # far beyond the batch's worktree_reference files (D-011/O-003) — Read/Grep/Glob stay
    # available for the legitimate cross-file lookups the worktree_reference hint permits.
    disallowed_tools = list(FINDINGS_DISALLOWED_TOOLS) if adapter.supports_tool_restriction else None
    cli_display = adapter.cli_name.value.capitalize()
    aggregated_raw = []
    findings_failed = False
    batches_attempted = 0
    batches_succeeded = 0
    # Distinct reasons the batches gave, in first-seen order. Without these the
    # step reports "0/N batches produced output" and the actual cause — a spent
    # quota, a timeout, a missing binary — is only recoverable by correlating
    # debug lines from the same second.
    batch_failure_reasons: list[str] = []
    # Paths whose batch actually produced output — a failed/skipped batch's files were
    # NOT reviewed, and nothing downstream may claim they were.
    reviewed_paths: set[str] = set()
    # Every path in the PR, so a batch can tell a hallucinated path apart from a real
    # file it simply was not shown. An empty set (no manifest) makes every unknown path
    # read as hallucinated, which is the safe direction: both outcomes drop the finding.
    change_manifest = ctx.get("change_manifest")
    manifest_paths = {f.path for f in change_manifest.files} if change_manifest else set()
    findings_out_of_scope = 0
    out_of_scope_findings: list[dict] = []
    # Questions the session opened and found unfounded. Kept apart from findings because
    # "checked, it is fine" is an answer, and without it a deliberate dismissal is
    # indistinguishable from a question nobody looked at.
    dismissed_questions: list[dict] = []
    batch_queue = list(batches)
    ctx.textual.dim_text(f"Reviewing {len(batch_queue)} batch(es) with {cli_display}")

    # Phase 1 — budget fitting stays sequential and deterministic: splits/degradations
    # requeue, so the set of ready-to-execute batches isn't known until this loop
    # reaches a fixpoint. No AI calls happen here.
    ready: list[tuple] = []  # (batch, prompt, effort)
    while batch_queue:
        batch = batch_queue.pop(0)
        prompt_parts = build_findings_prompt_parts(batch)
        prompt = prompt_parts["prompt"]
        fitted_batches, changed = get_prompt_budget_manager().fit_batch_to_budget(
            batch,
            prompt_parts,
            budget.deep_max_prompt_chars,
            allow_file_reads=ctx.data.get("review_file_reads_allowed", True),
        )
        if changed:
            logger.debug(
                "findings_batch_rebalanced",
                original_batch_id=batch.batch_id,
                produced_batches=[candidate.batch_id for candidate in fitted_batches],
                prompt_actual_chars=len(prompt),
                prompt_budget_target_chars=budget.deep_max_prompt_chars,
            )
            is_actual_split = len(fitted_batches) > 1 or fitted_batches[0].batch_id != batch.batch_id
            if is_actual_split:
                _render_findings_batch_split(
                    ctx,
                    batch.batch_id,
                    [candidate.batch_id for candidate in fitted_batches],
                )
            else:
                _render_findings_batch_degraded(ctx, batch.batch_id)
            batch_queue = fitted_batches + batch_queue
            continue

        batch = fitted_batches[0]
        batches_attempted += 1
        prompt_parts = build_findings_prompt_parts(batch)
        prompt = prompt_parts["prompt"]
        prompt_breakdown = summarize_findings_prompt_parts(prompt_parts)
        _log_ai_prompt(
            step_name="ai_review_findings",
            cli_name=adapter.cli_name.value,
            prompt=prompt,
            batch_id=batch.batch_id,
            files_context=len(batch.files_context),
            related_files=len(batch.related_files),
            checklist_items=len(batch.checklist_applicable),
            comment_entries=len(batch.comment_context),
            strategy=None,
            prompt_budget_target_chars=budget.deep_max_prompt_chars,
            prompt_actual_chars=len(prompt),
            prompt_still_too_large=batch.prompt_still_too_large,
            degraded_context=batch.degraded_context,
            **prompt_breakdown,
        )
        if len(prompt) > budget.deep_max_prompt_chars:
            findings_failed = True
            logger.error(
                "findings_batch_over_budget",
                batch_id=batch.batch_id,
                prompt_budget_target_chars=budget.deep_max_prompt_chars,
                prompt_actual_chars=len(prompt),
            )
            skipped_paths = ", ".join(sorted(batch.files_context)) or "unknown files"
            ctx.textual.warning_text(
                f"⚠ {batch.batch_id} skipped — too large even after reduction. "
                f"NOT reviewed: {skipped_paths}"
            )
            continue
        worktree_reference_count = sum(
            1 for entry in batch.files_context.values() if entry.worktree_reference
        )
        # A worktree_reference batch is the one shape shown to reliably drive O-003's
        # duration/timeout problem (D-011) — capping effort only here, not on every batch,
        # leaves batches that already complete quickly untouched.
        effort = (
            FINDINGS_WORKTREE_REFERENCE_EFFORT
            if worktree_reference_count and adapter.supports_effort_control
            else None
        )
        _render_findings_batch_started(ctx, batch)
        ready.append((batch, prompt, effort))

    # Phase 2 — execute ready batches through a small worker pool. Adapter calls are
    # independent subprocesses, so the only sequential cost was the loop itself
    # (real baseline: 307s wall for 6 batches, PR #3596). Workers never touch the UI;
    # results render here, on the step thread, as each batch completes.
    def _run(entry: tuple) -> dict:
        entry_batch, entry_prompt, entry_effort = entry
        try:
            return _execute_findings_batch(
                adapter,
                entry_batch,
                entry_prompt,
                project_root=project_root,
                findings_schema=findings_schema,
                disallowed_tools=disallowed_tools,
                effort=entry_effort,
                use_structured_output=use_structured_output,
                strategy_name=None,
                timeout_seconds=deep_call_timeout_seconds(
                    budget, len(entry_batch.files_context)
                ),
                manifest_paths=manifest_paths,
            )
        except Exception as exc:
            logger.error("findings_batch_crashed", batch_id=entry_batch.batch_id, error=str(exc))
            return {"status": "failed", "raw": None, "detail": f"adapter error: {exc}"}

    if ready:
        pool_size = min(
            FINDINGS_BATCH_CONCURRENCY, len(ready)
        )
        with ctx.textual.loading(
            f"Asking {cli_display} to review {len(ready)} batch(es)"
            + (f" ({pool_size} in parallel)…" if pool_size > 1 else "…")
        ):
            if pool_size == 1:
                completed = ((entry[0], _run(entry)) for entry in ready)
                outcomes = list(completed)
            else:
                import contextvars
                from concurrent.futures import ThreadPoolExecutor, as_completed

                # Each worker runs inside a copy of this thread's context, so the log's
                # run id (and anything else bound around the workflow) survives into the
                # pool. A pool worker otherwise starts with an empty context, which is
                # what left thousands of batch events unattributable to their run.
                def _run_in_context(entry, _ctx=None):
                    return (_ctx or contextvars.copy_context()).run(_run, entry)

                with ThreadPoolExecutor(max_workers=pool_size) as executor:
                    future_to_batch = {
                        executor.submit(_run_in_context, entry, contextvars.copy_context()): entry[0]
                        for entry in ready
                    }
                    outcomes = [
                        (future_to_batch[future], future.result())
                        for future in as_completed(future_to_batch)
                    ]

        for batch, outcome in outcomes:
            resolved = [(batch, outcome)]
            if (
                outcome["status"] == "failed"
                and outcome.get("timed_out")
                and any(entry.worktree_reference for entry in batch.files_context.values())
            ):
                # A timed-out worktree_reference batch means the CLI spent the whole
                # budget exploring a (usually huge) file and reviewed NOTHING. One
                # bounded retry with inline hunks trades depth for guaranteed
                # coverage of the batch's files, split across calls when one does not
                # fit; an empty list means nothing could be retried and the original
                # timeout stands.
                retried = _retry_timed_out_worktree_batch(ctx, batch, _run, budget)
                if retried:
                    resolved = retried
            for resolved_batch, resolved_outcome in resolved:
                if resolved_outcome["status"] == "success":
                    batches_succeeded += 1
                    dismissed_questions.extend(resolved_outcome.get("dismissed") or [])
                    reviewed_paths.update(resolved_batch.files_context)
                    findings_out_of_scope += resolved_outcome.get("out_of_scope", 0)
                    out_of_scope_findings.extend(resolved_outcome.get("out_of_scope_findings") or [])
                    aggregated_raw.extend(resolved_outcome["raw"])
                    _render_findings_batch_result(
                        ctx,
                        resolved_batch.batch_id,
                        status="success",
                        findings_count=len(resolved_outcome["raw"]),
                    )
                else:
                    findings_failed = True
                    reason = resolved_outcome.get("detail")
                    if reason and reason not in batch_failure_reasons:
                        batch_failure_reasons.append(reason)
                    _render_findings_batch_result(
                        ctx,
                        resolved_batch.batch_id,
                        status="failed",
                        detail=resolved_outcome["detail"],
                    )

    if batches_attempted and not batches_succeeded:
        # Every batch failed or was skipped: an "empty" review here means the AI never
        # ran, not that the code is clean. Publish empty findings so downstream steps
        # (and the worktree cleanup) still run via on_error: continue, but fail the step
        # visibly instead of masquerading as a clean review.
        ctx.data["raw_findings"] = build_default_findings()
        ctx.data["ai_findings_failed"] = True
        why = "; ".join(batch_failure_reasons) if batch_failure_reasons else ""
        logger.error(
            "findings_all_batches_failed",
            batches_attempted=batches_attempted,
            reasons=batch_failure_reasons,
            reason=why or None,
        )
        ctx.textual.error_text(
            f"AI findings failed: 0 of {batches_attempted} batch(es) produced output"
            + (f" — {why}. " if why else ". ")
            + "No code was reviewed — do not treat this as a clean review."
        )
        ctx.textual.end_step("error")
        return Error(
            f"AI findings failed: 0/{batches_attempted} batches produced output"
            + (f" — {why}" if why else "")
        )

    # There used to be an empty-findings rescue here: when batches succeeded and returned
    # nothing, it reviewed up to two "borderline" files on the theory that an empty result
    # meant candidate selection had been too aggressive. Deleted deliberately. A review
    # that has nothing to say has to be allowed to say nothing, and a step that reaches
    # for more files when the answer is "no problems found" is pressure to produce a
    # finding. The condition it was compensating for is gone anyway: it existed because
    # only 12 files of any PR were ever looked at, so an empty result really could mean
    # the wrong 12 were chosen.

    ctx.data["raw_findings"] = aggregated_raw or build_default_findings()
    ctx.data["ai_findings_failed"] = findings_failed
    if batches_attempted > 1:
        # With one batch its own line already said this.
        ctx.textual.success_text(f"✓ AI returned {len(ctx.data['raw_findings'])} raw finding(s)")
    if findings_failed:
        ctx.textual.warning_text("Some findings batches failed or were skipped due to budget limits.")
    if findings_out_of_scope:
        # Shown, not just logged: a model naming files it was never given is a signal
        # about the prompt, and it is the first thing to look at if packed batches ever
        # start losing real findings.
        _render_out_of_scope_findings(ctx, out_of_scope_findings)
    ctx.data["findings_out_of_scope"] = findings_out_of_scope
    _render_settled_questions(ctx, batches, dismissed_questions, ctx.data["raw_findings"])
    ctx.textual.end_step("success")
    return Success(
        "AI findings retrieved",
        metadata={
            "ai_findings_failed": findings_failed,
        },
    )


def normalize_findings(ctx: WorkflowContext) -> WorkflowResult:
    """
    Parse and validate raw AI output into Finding models.

    Accepts raw_findings as either a JSON string or a list of dicts.
    Each item is validated as a Finding model. Invalid items are skipped
    with a warning rather than failing the entire step.

    Requires (from ctx.data):
        raw_findings (list | str): Raw AI output from ai_review_findings

    Outputs (saved to ctx.data):
        normalized_findings (List[Finding]): Validated Finding objects

    Returns:
        Success or Error
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

    ctx.data["normalized_findings"] = findings

    summary = f"✓ {len(findings)} finding(s) normalized"
    if skipped:
        summary += f" ({skipped} skipped)"
    ctx.textual.success_text(summary)
    ctx.textual.end_step("success")
    return Success("Findings normalized")


def dedupe_findings(ctx: WorkflowContext) -> WorkflowResult:
    """
    Remove findings that duplicate existing PR comments.

    Uses the is_duplicate() validator to compare each finding against the
    existing_comments_index. A finding is a duplicate if it targets the same
    file, the same area (within 5 lines), and the same topic (same category
    or similar title).

    Requires (from ctx.data):
        normalized_findings (List[Finding])
        existing_comments_index (List[ExistingCommentIndexEntry])

    Outputs (saved to ctx.data):
        deduped_findings (List[Finding]): Findings after duplicate removal

    Returns:
        Success or Error
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

    ctx.data["deduped_findings"] = deduped

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
    return Success("Findings deduplicated", metadata={"deduped_findings_count": len(deduped)})


# ============================================================================
# PHASE 5: UI + SUBMIT
# ============================================================================


def build_new_comment_actions(ctx: WorkflowContext) -> WorkflowResult:
    """
    Convert deduplicated findings into ReviewActionProposal objects.

    Requires (from ctx.data):
        deduped_findings (List[Finding])

    Outputs (saved to ctx.data):
        review_action_proposals (List[ReviewActionProposal])

    Returns:
        Success or Skip (no findings)
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Build Comment Actions")

    findings = ctx.get("deduped_findings", [])
    manifest = ctx.get("change_manifest")
    batches = ctx.get("review_context_batches", [])

    if not findings:
        ctx.textual.dim_text("No findings to convert into actions.")
        ctx.textual.end_step("skip")
        return Skip("No findings to submit")

    actions = build_new_comment_actions_operation(findings)
    manifest_files = {file.path: file for file in getattr(manifest, "files", [])}
    read_modes = {
        path: entry.read_mode.value if entry.read_mode else None
        for batch in batches or []
        for path, entry in batch.files_context.items()
    }
    enriched_actions = []
    for action in actions:
        file_entry = manifest_files.get(action.path)
        enriched_actions.append(
            action.model_copy(
                update={
                    "file_status": str(file_entry.status) if file_entry else None,
                    "is_test_file": bool(file_entry.is_test) if file_entry else False,
                    "read_mode": read_modes.get(action.path),
                }
            )
        )
    actions = enriched_actions
    ctx.data["review_action_proposals"] = actions

    ctx.textual.success_text(f"✓ {len(actions)} action(s) ready for review")
    ctx.textual.end_step("success")
    return Success("Actions built")


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

    if cleanup_worktree_operation(ctx.git, ctx.data["worktree_path"]):
        ctx.textual.dim_text("Review worktree removed (no longer needed).")
        ctx.data["worktree_created"] = False
        ctx.data["worktree_path"] = None
    else:
        logger.warning("early_worktree_release_failed", worktree_path=ctx.data.get("worktree_path"))


def validate_review_actions(ctx: WorkflowContext) -> WorkflowResult:
    """
    Present each ReviewActionProposal to the user for approval, editing, or skipping.

    Requires (from ctx.data):
        review_action_proposals (List[ReviewActionProposal])

    Optional (from ctx.data):
        review_diff (str): Full PR diff for extracting diff context per comment

    Outputs (saved to ctx.data):
        approved_action_proposals (List[ReviewActionProposal])

    Returns:
        Success, Skip (none approved), or Error
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

    Requires (from ctx.data):
        approved_action_proposals (List[ReviewActionProposal])
        review_pr_number (int)

    Optional (from ctx.data):
        review_commit_sha (str): Head commit SHA (fetched if missing)
        review_diff (str): Full PR diff for inline comment validation

    Returns:
        Success, Skip (no approved actions), or Error
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
                event=event,
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

    Requires (from ctx.data):
        review_threads (List[UICommentThread]): Unresolved inline review threads
        review_pr (UIPullRequest): PR object with author info
        review_current_user (str): GitHub login running Titan

    Outputs (saved to ctx.data):
        thread_review_candidates (List[ThreadReviewCandidate])

    Returns:
        Success, Skip (no candidates), or Error
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

    Requires (from ctx.data):
        thread_review_candidates (List[ThreadReviewCandidate])
        review_threads (List[UICommentThread]): For extracting reply history
        review_diff (str): Full PR unified diff

    Requires:
        ctx.github: Optional GitHub client used to inspect referenced commits.

    Outputs (saved to ctx.data):
        thread_review_contexts (List[ThreadReviewContext])

    Returns:
        Success, Skip (no candidates), or Error
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

    Requires (from ctx.data):
        thread_review_contexts (List[ThreadReviewContext])

    Outputs (saved to ctx.data):
        raw_thread_decisions (list): Raw AI output aggregated across batches, before normalization

    Returns:
        Success or Error
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

    Requires (from ctx.data):
        raw_thread_decisions (list | str): Raw AI output from ai_thread_resolution

    Outputs (saved to ctx.data):
        thread_decisions (List[ThreadDecision]): Validated ThreadDecision objects

    Returns:
        Success or Error
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

    Requires (from ctx.data):
        thread_decisions (List[ThreadDecision])
        thread_review_contexts (List[ThreadReviewContext])

    Outputs (saved to ctx.data):
        review_action_proposals (List[ReviewActionProposal])

    Returns:
        Success, Skip (no actionable decisions), or Error
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
