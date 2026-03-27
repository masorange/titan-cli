"""
Steps for AI-powered PR code review.

This module contains steps for reviewing pull requests authored by others using
AI analysis combined with project-specific skill guidelines.
"""
import logging
import threading
from typing import List

from rich.markup import escape as escape_markup

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Exit, Skip
from titan_cli.core.result import ClientSuccess, ClientError
from titan_cli.external_cli.adapters import HEADLESS_ADAPTER_REGISTRY, get_headless_adapter
from titan_cli.ui.tui.widgets import ChoiceOption, OptionItem, PromptChoice

from ..models.view import UIReviewSuggestion
from ..operations.ai_review_operations import build_refinement_prompt, parse_reply_suggestion
from ..operations.code_review_operations import (
    select_files_for_review,
    build_review_context,
    build_pr_summary_prompt,
    extract_diff_for_file,
    extract_hunk_for_line,
    build_review_payload,
    compute_diff_stat,
    filter_own_duplicate_suggestions,
)

logger = logging.getLogger(__name__)


# ============================================================================
# UI HELPERS
# ============================================================================


def _show_suggestion_and_get_action(
    ctx: WorkflowContext,
    suggestion: UIReviewSuggestion,
    idx: int,
    total: int,
    can_refine: bool = False,
) -> str:
    """
    Display a review suggestion and return the user's chosen action.

    Returns:
        "approve", "edit", "refine", "skip", or "exit"
    """
    # Display header with comment number
    ctx.textual.text("")
    if suggestion.reply_to_comment_id:
        ctx.textual.bold_text(f"Comment {idx + 1} of {total} — Reply to existing thread #{suggestion.reply_to_comment_id}")
    else:
        ctx.textual.bold_text(f"Comment {idx + 1} of {total}")
    ctx.textual.text("")

    # Mount the ReviewSuggestion widget (handles all display: severity, file, line, diff, body)
    from titan_plugin_github.widgets import ReviewSuggestion
    ctx.textual.mount(ReviewSuggestion(suggestion))
    ctx.textual.text("")

    # Build options
    options = [
        ChoiceOption(value="approve", label="✓ Approve", variant="success"),
        ChoiceOption(value="edit", label="✎ Edit", variant="default"),
    ]
    if can_refine:
        options.append(ChoiceOption(value="refine", label="↻ Refine", variant="primary"))
    options.append(ChoiceOption(value="skip", label="— Skip", variant="default"))
    if idx < total - 1:
        options.append(ChoiceOption(value="exit", label="✗ Exit review", variant="error"))

    result_container: dict = {}
    result_event = threading.Event()

    def on_choice(value):
        result_container["choice"] = value
        result_event.set()

    prompt = PromptChoice(
        question="What would you like to do with this comment?",
        options=options,
        on_select=on_choice,
    )
    ctx.textual.mount(prompt)
    result_event.wait()

    choice = result_container.get("choice", "skip")

    # Replace buttons with a decision badge
    action_labels = {
        "approve": "✓ Approved",
        "edit": "✎ Edited",
        "refine": "↻ Refining…",
        "skip": "— Skipped",
        "exit": "✗ Exit review",
    }
    action_variants = {
        "approve": "success",
        "edit": "default",
        "refine": "primary",
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
            title=f"⭐ #{pr.number}: {pr.title}" if pr.number in assigned_numbers else f"#{pr.number}: {pr.title}",
            description=f"by {pr.author_name} · {pr.branch_info}",
        )
        for pr in sorted_prs
    ]

    assigned_count = len(assigned_numbers)
    question = f"Select a PR to review ({len(all_prs_list)} total{f', {assigned_count} asignados ⭐' if assigned_count else ''}):"

    try:
        selected = ctx.textual.ask_option(question, options)
    except Exception as e:
        ctx.textual.end_step("error")
        return Error(str(e))

    if not selected:
        ctx.textual.warning_text("No PR selected")
        ctx.textual.end_step("skip")
        return Exit("User cancelled PR selection")

    selected_pr = next((pr for pr in sorted_prs if pr.number == selected), None)
    if not selected_pr:
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


def fetch_pr_changes(ctx: WorkflowContext) -> WorkflowResult:
    """
    Fetch and display PR changes, including diff and existing comments.

    Requires (from ctx.data):
        review_pr_number (int): PR number

    Outputs (saved to ctx.data):
        review_changed_files (List[str]): List of changed file paths
        review_diff (str): Full unified diff
        review_pr (UIPullRequest): Pull request details
        review_threads (List[UICommentThread]): Existing review threads and comments

    Returns:
        Success, Skip (empty diff), or Error
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Fetch PR Changes")

    pr_number = ctx.get("review_pr_number")
    if not pr_number:
        ctx.textual.end_step("error")
        return Error("No PR number in context (run select_pr_for_code_review first)")

    if not ctx.github:
        ctx.textual.end_step("error")
        return Error("GitHub client not available")

    # Fetch PR details, files, diff, and commit SHA in parallel-ish sequence
    with ctx.textual.loading(f"Fetching PR #{pr_number} data..."):
        pr_result = ctx.github.get_pull_request(pr_number)
        files_result = ctx.github.get_pr_files(pr_number)
        diff_result = ctx.github.get_pr_diff(pr_number)
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
        case ClientSuccess(data=changed_files):
            pass
        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to fetch changed files: {err}")
            ctx.textual.end_step("error")
            return Error(f"Failed to fetch files: {err}")

    # Validate diff — fallback to per-file diffs if PR is too large
    match diff_result:
        case ClientSuccess(data=diff):
            if not diff or not diff.strip():
                ctx.textual.dim_text("PR diff is empty — nothing to review.")
                ctx.textual.end_step("skip")
                return Skip("Empty PR diff")
        case ClientError(error_message=err) if "too_large" in err or "too large" in err.lower():
            ctx.textual.warning_text("PR diff is too large. Fetching file stats to select what matters...")

            # Step 1: Get all files with stats (no patches yet)
            with ctx.textual.loading("Fetching file stats..."):
                files_stats_result = ctx.github.get_pr_files_with_stats(pr_number)

            match files_stats_result:
                case ClientSuccess(data=files_with_stats):
                    pass
                case ClientError(error_message=err):
                    ctx.textual.end_step("error")
                    return Error(f"Could not fetch file stats: {err}")

            # Step 2: AI selects which files actually matter
            if ctx.ai:
                with ctx.textual.loading(f"AI selecting important files from {len(files_with_stats)} changed..."):
                    selected_files = select_files_for_review(files_with_stats, ctx.ai)
            else:
                from ..operations.code_review_operations import MAX_FILES_FOR_REVIEW
                selected_files = [f.path for f in files_with_stats[:MAX_FILES_FOR_REVIEW]]

            ctx.textual.dim_text(f"Reviewing {len(selected_files)} of {len(files_with_stats)} files")
            changed_files = selected_files

            # Step 3: Fetch patches only for selected files
            with ctx.textual.loading("Fetching patches for selected files..."):
                patches_result = ctx.github.get_pr_file_patches(pr_number, selected_files)

            match patches_result:
                case ClientSuccess(data=patches_diff) if patches_diff:
                    diff = patches_diff
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

    # Display file changes summary using diff stat
    formatted_files, formatted_summary = compute_diff_stat(diff)
    ctx.textual.show_diff_stat(
        formatted_files,
        formatted_summary,
        title="Files affected:",
    )

    # Fetch review threads and general comments
    review_threads = []
    with ctx.textual.loading("Fetching existing review comments..."):
        threads_result = ctx.github.get_pr_review_threads(pr_number, include_resolved=False)
        match threads_result:
            case ClientSuccess(data=threads):
                review_threads = threads
            case ClientError():
                pass

        general_result = ctx.github.get_pr_general_comments(pr_number)
        match general_result:
            case ClientSuccess(data=general):
                review_threads += general
            case ClientError():
                pass

    if review_threads:
        ctx.textual.dim_text(f"{len(review_threads)} existing comment(s)")

    ctx.textual.end_step("success")

    return Success(
        f"Fetched PR #{pr_number} data",
        metadata={
            "review_changed_files": changed_files,
            "review_diff": diff,
            "review_pr": pr,
            "review_threads": review_threads,
        },
    )


def ai_review_pr(ctx: WorkflowContext) -> WorkflowResult:
    """
    Use AI to generate review comments for the PR.

    Requires (from ctx.data):
        review_pr (UIPullRequest)
        review_diff (str)
        review_changed_files (List[str])
        review_skills (List[dict])

    Outputs (saved to ctx.data):
        review_suggestions (List[UIReviewSuggestion]): with diff_context filled in

    Returns:
        Success, Skip (no comments), or Error
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("AI Code Review")

    pr = ctx.get("review_pr")
    diff = ctx.get("review_diff", "")
    skills = ctx.get("review_skills", [])
    docs = ctx.get("review_docs", [])
    threads = ctx.get("review_threads", [])

    if not pr or not diff:
        ctx.textual.end_step("error")
        return Error("Missing PR data (run fetch_pr_changes first)")

    if not ctx.ai:
        ctx.textual.error_text("AI client not available")
        ctx.textual.end_step("error")
        return Error("AI client not available")

    # Get current user to filter out their own comments from the context
    current_user = None
    if ctx.github:
        user_result = ctx.github.get_current_user()
        match user_result:
            case ClientSuccess(data=login):
                current_user = login
            case ClientError():
                pass  # Best effort — continue without filtering

    from ..agents.code_review_agent import CodeReviewAgent

    context_str = build_review_context(pr, diff, skills, docs, threads, current_user)

    with ctx.textual.loading("Generating AI review comments..."):
        agent = CodeReviewAgent(ctx.ai)
        suggestions = agent.review(context_str)

    if not suggestions:
        ctx.textual.dim_text("AI found no issues to comment on.")
        ctx.textual.end_step("skip")
        return Skip("No AI review suggestions generated")

    # Enrich suggestions with the specific hunk around the commented line
    from ..operations.code_review_operations import find_line_by_snippet
    for suggestion in suggestions:
        file_diff = extract_diff_for_file(diff, suggestion.file_path)
        if file_diff:
            # If we have a snippet but no line, resolve the snippet to a line first
            target_line = suggestion.line
            if suggestion.snippet and not target_line:
                target_line = find_line_by_snippet(file_diff, suggestion.snippet)
                if target_line:
                    # Update the suggestion object with the resolved line
                    suggestion.line = target_line

            # Extract the hunk around the target line
            hunk = extract_hunk_for_line(file_diff, target_line)
            suggestion.diff_context = hunk or file_diff[:3000]

    # Post-process: filter suggestions that duplicate own existing comments
    own_threads = ctx.get("review_threads", [])
    own_threads_by_user = [
        t for t in own_threads
        if current_user and t.main_comment.author_login == current_user
    ]
    if own_threads_by_user:
        suggestions, duplicates = filter_own_duplicate_suggestions(suggestions, own_threads_by_user)
        if duplicates:
            ctx.textual.dim_text(
                f"  {len(duplicates)} suggestion(s) removed — already commented by you"
            )

    if not suggestions:
        ctx.textual.dim_text("AI found no new issues to comment on (all were duplicates of your existing comments).")
        ctx.textual.end_step("skip")
        return Skip("No new AI review suggestions (all duplicates filtered)")

    # Show summary
    counts = {"critical": 0, "improvement": 0, "suggestion": 0}
    for s in suggestions:
        counts[s.severity] = counts.get(s.severity, 0) + 1

    ctx.textual.success_text(f"Generated {len(suggestions)} review comment(s):")
    if counts["critical"]:
        ctx.textual.error_text(f"  🔴 {counts['critical']} critical")
    if counts["improvement"]:
        ctx.textual.warning_text(f"  🟡 {counts['improvement']} improvement(s)")
    if counts["suggestion"]:
        ctx.textual.dim_text(f"  🔵 {counts['suggestion']} suggestion(s)")

    ctx.textual.end_step("success")

    return Success(
        f"Generated {len(suggestions)} review comment(s)",
        metadata={"review_suggestions": suggestions},
    )


def summarize_pr_review(ctx: WorkflowContext) -> WorkflowResult:
    """
    Generate and display an AI summary of the PR before validating comments.

    Requires (from ctx.data):
        review_pr (UIPullRequest)
        review_changed_files (List[str])
        review_suggestions (List[UIReviewSuggestion])

    Returns:
        Success or Skip (if AI unavailable)
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("PR Review Summary")

    pr = ctx.get("review_pr")
    changed_files = ctx.get("review_changed_files", [])
    suggestions = ctx.get("review_suggestions", [])

    if not pr:
        ctx.textual.end_step("skip")
        return Skip("No PR data available")

    if not ctx.ai:
        ctx.textual.end_step("skip")
        return Skip("AI client not available")

    prompt = build_pr_summary_prompt(pr, changed_files, suggestions)

    from titan_cli.ai.models import AIMessage
    with ctx.textual.loading("Generating PR summary..."):
        try:
            response = ctx.ai.generate(
                messages=[AIMessage(role="user", content=prompt)],
                max_tokens=600,
                temperature=0.3,
            )
            summary = response.content.strip()
        except Exception as e:
            ctx.textual.warning_text(f"Could not generate summary: {e}")
            ctx.textual.end_step("skip")
            return Skip("Summary generation failed")

    ctx.textual.markdown(summary)
    ctx.textual.end_step("success")
    return Success("PR summary generated")


def validate_review_comments(ctx: WorkflowContext) -> WorkflowResult:
    """
    Present each AI suggestion to the user for approval, editing, refining, or skipping.

    Requires (from ctx.data):
        review_suggestions (List[UIReviewSuggestion])

    Optional (from ctx.data):
        cli_preference (str): Which headless CLI to use for refinement (default "auto")
        review_diff (str): PR diff for snippet context during refinement
        timeout (int): CLI timeout in seconds (default 60)

    Outputs (saved to ctx.data):
        approved_suggestions (List[UIReviewSuggestion])

    Returns:
        Success, Skip (none approved), or Error
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Validate Review Comments")

    suggestions: List[UIReviewSuggestion] = ctx.get("review_suggestions", [])

    if not suggestions:
        ctx.textual.dim_text("No suggestions to validate.")
        ctx.textual.end_step("skip")
        return Skip("No suggestions to validate")

    # Resolve CLI adapter for Refine option (best effort — may be None)
    cli_preference = ctx.data.get("cli_preference", "auto")
    timeout = int(ctx.data.get("timeout", 60))
    diff = ctx.get("review_diff", "")
    project_root = ctx.data.get("project_root")
    adapter = _resolve_headless_adapter(cli_preference)

    approved: List[UIReviewSuggestion] = []
    skipped = 0
    exit_requested = False

    # Sort by severity: critical → improvement → suggestion
    severity_order = {"critical": 0, "improvement": 1, "suggestion": 2}
    sorted_suggestions = sorted(
        suggestions,
        key=lambda s: severity_order.get(s.severity, 99),
    )

    for idx, suggestion in enumerate(sorted_suggestions):
        if exit_requested:
            break

        current = suggestion  # may be replaced after refinement

        while True:
            choice = _show_suggestion_and_get_action(
                ctx, current, idx, len(sorted_suggestions), can_refine=adapter is not None
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
                    approved.append(UIReviewSuggestion(
                        file_path=current.file_path,
                        line=current.line,
                        body=new_body.strip(),
                        severity=current.severity,
                        diff_context=current.diff_context,
                        snippet=current.snippet,
                    ))
                else:
                    ctx.textual.warning_text("Empty body, comment skipped")
                    skipped += 1
                break

            elif choice == "refine" and adapter:
                ctx.textual.text("")
                feedback = ctx.textual.ask_multiline(
                    "What should the AI improve in this suggestion?",
                )
                if not feedback or not feedback.strip():
                    ctx.textual.dim_text("No feedback provided, showing suggestion again.")
                    continue

                refine_prompt = build_refinement_prompt(
                    original_comment=f"Review comment for `{current.file_path}`:\n{current.body}",
                    existing_replies=[],
                    diff_snippet=current.diff_context or (diff[:8_000] if diff else None),
                    user_feedback=feedback,
                    previous_suggestion=current.body,
                )

                cli_display = adapter.cli_name.value.capitalize()
                with ctx.textual.loading(f"Refining with {cli_display}…"):
                    response = adapter.execute(refine_prompt, cwd=project_root, timeout=timeout)

                if not response.succeeded:
                    if response.stderr:
                        try:
                            ctx.textual.dim_text(escape_markup(response.stderr))
                        except Exception:
                            pass
                    ctx.textual.warning_text("Refinement failed — showing previous suggestion.")
                    continue

                refined_body = parse_reply_suggestion(response.stdout)
                if refined_body and refined_body.strip():
                    current = UIReviewSuggestion(
                        file_path=current.file_path,
                        line=current.line,
                        body=refined_body.strip(),
                        severity=current.severity,
                        diff_context=current.diff_context,
                        snippet=current.snippet,
                    )
                else:
                    ctx.textual.warning_text("Empty refinement — showing previous suggestion.")
                continue  # re-show refined suggestion

            else:  # skip
                skipped += 1
                break

    if not approved:
        ctx.textual.dim_text("No comments approved.")
        ctx.textual.end_step("skip")
        return Skip("No approved review comments")

    ctx.textual.success_text(
        f"✓ {len(approved)} comment(s) approved, {skipped} skipped"
    )
    ctx.textual.end_step("success")

    return Success(
        f"{len(approved)} comment(s) approved",
        metadata={"approved_suggestions": approved},
    )


def _resolve_headless_adapter(cli_preference: str):
    """Return the first available headless adapter, or None."""
    if cli_preference == "auto":
        for cli_name in HEADLESS_ADAPTER_REGISTRY:
            candidate = get_headless_adapter(cli_name)
            if candidate.is_available():
                return candidate
        return None

    try:
        candidate = get_headless_adapter(cli_preference)
    except ValueError:
        return None

    return candidate if candidate.is_available() else None


def submit_pr_review(ctx: WorkflowContext) -> WorkflowResult:
    """
    Submit the approved review comments as a GitHub review.

    Requires (from ctx.data):
        review_pr_number (int)
        approved_suggestions (List[UIReviewSuggestion])

    Returns:
        Success, Skip (no approved comments), or Error
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Submit Review")

    approved: List[UIReviewSuggestion] = ctx.get("approved_suggestions", [])
    pr_number = ctx.get("review_pr_number")
    commit_sha = ctx.get("review_commit_sha", "")
    diff = ctx.get("review_diff", "")

    if not pr_number:
        ctx.textual.end_step("error")
        return Error("No PR number in context")

    if not ctx.github:
        ctx.textual.end_step("error")
        return Error("GitHub client not available")

    # Get commit SHA if not available (needed for inline comments)
    if not commit_sha and approved:
        with ctx.textual.loading("Fetching latest commit SHA..."):
            sha_result = ctx.github.get_pr_commit_sha(pr_number)
        match sha_result:
            case ClientSuccess(data=sha):
                commit_sha = sha
            case ClientError(error_message=err):
                ctx.textual.error_text("No commit SHA available — cannot submit inline comments")
                ctx.textual.end_step("error")
                return Error(f"Missing commit SHA for inline review: {err}")

    # Show summary
    if approved:
        ctx.textual.text(f"Ready to submit {len(approved)} comment(s) on PR #{pr_number}")
    else:
        ctx.textual.warning_text("No review comments — you can still submit a review decision")
    ctx.textual.text("")

    # Ask review event type
    event_options = [
        OptionItem(value="COMMENT", title="💬 Comment", description="Post comments without approval decision"),
        OptionItem(value="REQUEST_CHANGES", title="🔴 Request Changes", description="Block merge until changes are made"),
        OptionItem(value="APPROVE", title="✅ Approve", description="Approve the PR"),
    ]

    try:
        event = ctx.textual.ask_option("Select review type:", event_options)
    except Exception as e:
        ctx.textual.end_step("error")
        return Error(str(e))

    if not event:
        ctx.textual.warning_text("Review cancelled")
        ctx.textual.end_step("skip")
        return Skip("User cancelled review submission")

    # Optional general body
    ctx.textual.text("")
    add_body = ctx.textual.ask_confirm(
        "Add a general review comment (optional)?",
        default=False,
    )
    review_body = ""
    if add_body:
        review_body = ctx.textual.ask_multiline("General review comment:", default="")

    # Build payload — always create as PENDING, submit separately with the chosen event
    payload = build_review_payload(approved, commit_sha, diff)

    if review_body and review_body.strip():
        existing_body = payload.get("body", "")
        payload["body"] = (existing_body + "\n\n" + review_body.strip()).strip()

    # Create draft review (PENDING)
    with ctx.textual.loading("Creating review..."):
        draft_result = ctx.github.create_draft_review(pr_number, payload)

    match draft_result:
        case ClientSuccess(data=review_id):
            ctx.textual.success_text(f"✓ Review #{review_id} created")
        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to create review: {err}")
            ctx.textual.end_step("error")
            return Error(f"Failed to create draft review: {err}")

    with ctx.textual.loading("Submitting review..."):
        submit_result = ctx.github.submit_review(pr_number, review_id, event, review_body)

    match submit_result:
        case ClientSuccess():
            ctx.textual.success_text(
                f"✓ Review submitted as '{event}' on PR #{pr_number} "
                f"with {len(approved)} comment(s)"
            )
            ctx.textual.end_step("success")
            return Success(f"Review submitted on PR #{pr_number}")
        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to submit review: {err}")
            ctx.textual.end_step("error")
            return Error(f"Failed to submit review: {err}")
