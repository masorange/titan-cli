"""
Steps for AI-powered PR code review.

This module contains steps for reviewing pull requests authored by others using
AI analysis combined with project-specific skill guidelines.
"""
import threading
from typing import List

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Exit, Skip
from titan_cli.core.result import ClientSuccess, ClientError
from titan_cli.ui.tui.widgets import ChoiceOption, OptionItem

from ..models.view import UIReviewSuggestion
from ..operations.code_review_operations import (
    load_all_project_skills,
    select_relevant_skills,
    build_review_context,
    extract_diff_for_file,
    extract_hunk_for_line,
    build_review_payload,
    compute_diff_stat,
)


# ============================================================================
# UI HELPERS
# ============================================================================


def _show_suggestion_and_get_action(
    ctx: WorkflowContext,
    suggestion: UIReviewSuggestion,
    idx: int,
    total: int,
) -> str:
    """
    Display a review suggestion and return the user's chosen action.

    Returns:
        "approve", "edit", "skip", or "exit"
    """
    # Display header with comment number
    ctx.textual.text("")
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
        ChoiceOption(value="skip", label="— Skip", variant="default"),
    ]
    if idx < total - 1:
        options.append(ChoiceOption(value="exit", label="✗ Exit review", variant="error"))

    result_container: dict = {}
    result_event = threading.Event()

    def on_choice(value):
        result_container["choice"] = value
        result_event.set()

    from titan_cli.ui.tui.widgets import PromptChoice
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
    List PRs pending review and ask user to select one.

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

    with ctx.textual.loading("Fetching PRs pending your review..."):
        result = ctx.github.list_pending_review_prs()

    match result:
        case ClientSuccess(data=prs):
            if not prs:
                ctx.textual.dim_text("No PRs are currently assigned for your review.")
                ctx.textual.end_step("skip")
                return Exit("No PRs pending review")

            options = [
                OptionItem(
                    value=pr.number,
                    title=f"#{pr.number}: {pr.title}",
                    description=f"by {pr.author_name} · {pr.branch_info}",
                )
                for pr in prs
            ]

            try:
                selected = ctx.textual.ask_option(
                    f"Select a PR to review ({len(prs)} assigned):",
                    options,
                )
            except Exception as e:
                ctx.textual.end_step("error")
                return Error(str(e))

            if not selected:
                ctx.textual.warning_text("No PR selected")
                ctx.textual.end_step("skip")
                return Exit("User cancelled PR selection")

            selected_pr = next((pr for pr in prs if pr.number == selected), None)
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

        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to fetch PRs: {err}")
            ctx.textual.end_step("error")
            return Error(f"Failed to fetch PRs: {err}")


def fetch_pr_changes(ctx: WorkflowContext) -> WorkflowResult:
    """
    Fetch diff, changed files, latest commit SHA, and matching project skills.

    Requires (from ctx.data):
        review_pr_number (int): PR number

    Outputs (saved to ctx.data):
        review_changed_files (List[str])
        review_diff (str)
        review_commit_sha (str)
        review_skills (List[dict])
        review_pr (UIPullRequest)

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

    # Validate diff
    match diff_result:
        case ClientSuccess(data=diff):
            if not diff or not diff.strip():
                ctx.textual.dim_text("PR diff is empty — nothing to review.")
                ctx.textual.end_step("skip")
                return Skip("Empty PR diff")
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

    # Load all skills and select relevant ones via AI
    all_skills = load_all_project_skills()
    if all_skills and ctx.ai:
        with ctx.textual.loading("Selecting relevant project skills..."):
            skills = select_relevant_skills(all_skills, diff, ctx.ai)
    else:
        skills = all_skills

    # Display file changes summary using diff stat
    formatted_files, formatted_summary = compute_diff_stat(diff)
    ctx.textual.show_diff_stat(
        formatted_files,
        formatted_summary,
        title="Files affected:",
    )

    ctx.textual.text("")
    if skills:
        skill_names = ", ".join(s["name"] for s in skills)
        ctx.textual.success_text(f"✓ {len(skills)} project skill(s) loaded: {skill_names}")
    else:
        ctx.textual.dim_text("No project skills matched changed files")
    if commit_sha:
        ctx.textual.dim_text(f"  Latest commit: {commit_sha[:7]}")

    ctx.textual.end_step("success")

    return Success(
        f"Fetched PR #{pr_number} data",
        metadata={
            "review_changed_files": changed_files,
            "review_diff": diff,
            "review_commit_sha": commit_sha,
            "review_skills": skills,
            "review_pr": pr,
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
    changed_files = ctx.get("review_changed_files", [])
    skills = ctx.get("review_skills", [])

    if not pr or not diff:
        ctx.textual.end_step("error")
        return Error("Missing PR data (run fetch_pr_changes first)")

    if not ctx.ai:
        ctx.textual.error_text("AI client not available")
        ctx.textual.end_step("error")
        return Error("AI client not available")

    from ..agents.code_review_agent import CodeReviewAgent

    context_str = build_review_context(pr, diff, changed_files, skills)

    with ctx.textual.loading("Generating AI review comments..."):
        agent = CodeReviewAgent(ctx.ai)
        suggestions = agent.review(context_str)

    if not suggestions:
        ctx.textual.dim_text("AI found no issues to comment on.")
        ctx.textual.end_step("skip")
        return Skip("No AI review suggestions generated")

    # Enrich suggestions with the specific hunk around the commented line
    for suggestion in suggestions:
        file_diff = extract_diff_for_file(diff, suggestion.file_path)
        if file_diff:
            hunk = extract_hunk_for_line(file_diff, suggestion.line)
            suggestion.diff_context = hunk or file_diff[:3000]

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


def validate_review_comments(ctx: WorkflowContext) -> WorkflowResult:
    """
    Present each AI suggestion to the user for approval, editing, or skipping.

    Requires (from ctx.data):
        review_suggestions (List[UIReviewSuggestion])
        review_changed_files (List[str]): For display purposes

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

    approved: List[UIReviewSuggestion] = []
    skipped = 0

    # Sort by severity: critical → improvement → suggestion
    severity_order = {"critical": 0, "improvement": 1, "suggestion": 2}
    sorted_suggestions = sorted(
        suggestions,
        key=lambda s: severity_order.get(s.severity, 99),
    )

    for idx, suggestion in enumerate(sorted_suggestions):
        choice = _show_suggestion_and_get_action(ctx, suggestion, idx, len(sorted_suggestions))

        if choice == "exit":
            ctx.textual.warning_text(
                f"Exiting validation. Approved {len(approved)}, skipped {skipped}."
            )
            break

        elif choice == "approve":
            approved.append(suggestion)

        elif choice == "edit":
            ctx.textual.text("")
            new_body = ctx.textual.ask_multiline(
                "Edit the review comment:",
                default=suggestion.body,
            )
            if new_body and new_body.strip():
                edited = UIReviewSuggestion(
                    file_path=suggestion.file_path,
                    line=suggestion.line,
                    body=new_body.strip(),
                    severity=suggestion.severity,
                    diff_context=suggestion.diff_context,
                )
                approved.append(edited)
            else:
                ctx.textual.warning_text("Empty body, comment skipped")
                skipped += 1

        else:  # skip
            skipped += 1

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


def submit_pr_review(ctx: WorkflowContext) -> WorkflowResult:
    """
    Submit the approved review comments as a GitHub review.

    Requires (from ctx.data):
        review_pr_number (int)
        review_commit_sha (str)
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

    if not approved:
        ctx.textual.dim_text("No approved comments to submit.")
        ctx.textual.end_step("skip")
        return Skip("No approved comments")

    if not pr_number:
        ctx.textual.end_step("error")
        return Error("No PR number in context")

    if not ctx.github:
        ctx.textual.end_step("error")
        return Error("GitHub client not available")

    if not commit_sha:
        ctx.textual.error_text("No commit SHA available — cannot submit inline comments")
        ctx.textual.end_step("error")
        return Error("Missing commit SHA for review")

    # Show summary
    ctx.textual.text(f"Ready to submit {len(approved)} comment(s) on PR #{pr_number}")
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

    # Build payload
    payload = build_review_payload(approved, commit_sha)

    # If user chose APPROVE or REQUEST_CHANGES, override the event
    payload["event"] = event

    if review_body and review_body.strip():
        existing_body = payload.get("body", "")
        payload["body"] = (existing_body + "\n\n" + review_body.strip()).strip()

    # Create draft review and submit
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
