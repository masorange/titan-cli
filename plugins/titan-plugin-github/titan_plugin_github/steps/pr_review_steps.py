"""
Steps for reviewing and addressing PR comments.

This module contains steps for reviewing PR comments and UI helpers
to keep the main step functions clean and readable.
"""
import os
import threading
from typing import List, Dict
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Exit, Skip
from titan_cli.core.result import ClientSuccess, ClientError
from titan_cli.ui.tui.widgets import ChoiceOption, OptionItem
from titan_plugin_github.widgets import CommentThread
from ..models import UICommentThread
from ..operations import (
    fetch_pr_threads,
    setup_worktree,
    cleanup_worktree,
    commit_in_worktree,
    build_ai_review_context,
    find_ai_response_file,
    create_commit_message,
    reply_to_comment_batch,
    prepare_replies_for_sending,
)
from titan_plugin_git.operations import format_diff_stat_display


# ============================================================================
# UI HELPER FUNCTIONS (Private)
# ============================================================================


def _show_thread_and_get_action(
    ctx: WorkflowContext,
    pr_thread: UICommentThread,
    thread_idx: int,
    total_threads: int
) -> str:
    """
    Display a comment thread and get user's action choice.

    Args:
        ctx: Workflow context
        pr_thread: The PR review thread (UI model)
        thread_idx: Current thread index (0-based)
        total_threads: Total number of threads

    Returns:
        User's choice: "ai_review", "reply", "skip", "resolve", or "exit"
    """

    # Prepare action options
    options = [
        ChoiceOption(value="ai_review", label="AI Review & Fix", variant="primary"),
        ChoiceOption(value="reply", label="Reply manually", variant="default"),
        ChoiceOption(value="skip", label="Skip for now", variant="default"),
        ChoiceOption(value="resolve", label="Resolve thread", variant="success"),
    ]

    # Add "Exit" option if not the last thread
    if thread_idx < total_threads - 1:
        options.append(
            ChoiceOption(value="exit", label="Exit review", variant="error")
        )

    # Result container for callback
    result_container = {}
    result_event = threading.Event()

    def on_choice_selected(value):
        result_container["choice"] = value
        result_event.set()

    # Create and mount CommentThread widget
    thread_widget = CommentThread(
        thread=pr_thread,
        thread_number=f"Thread {thread_idx + 1} of {total_threads}",
        options=options,
        on_select=on_choice_selected
    )

    ctx.textual.text("")
    ctx.textual.mount(thread_widget)

    # Wait for user selection
    result_event.wait()
    choice = result_container.get("choice")

    # Replace the choice buttons with a DecisionBadge
    def replace_buttons_with_badge():
        from titan_cli.ui.tui.widgets import PromptChoice
        from titan_cli.ui.tui.widgets.decision_badge import DecisionBadge
        try:
            prompt_widget = thread_widget.query_one(PromptChoice)
            prompt_widget.remove()

            action_labels = {
                "ai_review": "✓ AI Review & Fix",
                "reply": "→ Reply manually",
                "skip": "— Skip",
                "resolve": "✓ Resolved",
                "exit": "✗ Exit review",
            }
            action_variants = {
                "ai_review": "success",
                "reply": "default",
                "skip": "default",
                "resolve": "success",
                "exit": "warning",
            }
            label = action_labels.get(choice, f"→ {choice}")
            variant = action_variants.get(choice, "default")
            thread_widget.mount(DecisionBadge(label, variant=variant))
        except Exception:
            pass

    ctx.textual.app.call_from_thread(replace_buttons_with_badge)

    return choice


def _handle_manual_reply(
    ctx: WorkflowContext,
    pr_thread: UICommentThread,
    pending_responses: Dict[int, str]
) -> bool:
    """
    Handle manual reply to a comment thread.

    Args:
        ctx: Workflow context
        pr_thread: The PR review thread
        pending_responses: Dict to accumulate responses for batch sending

    Returns:
        True if reply was added, False if skipped
    """
    ctx.textual.text("")
    reply_text = ctx.textual.ask_multiline(
        "Enter your reply:",
        default=""
    )

    if reply_text and reply_text.strip():
        main_comment_id = pr_thread.main_comment.id
        pending_responses[main_comment_id] = {"text": reply_text, "source": "manual"}
        ctx.textual.success_text("✓ Reply queued for review")
        return True
    else:
        ctx.textual.warning_text("Empty reply, skipping")
        return False


def _handle_ai_review(
    ctx: WorkflowContext,
    pr_thread: UICommentThread,
    worktree_path: str,
    pr_title: str,
    comment_commits: Dict[int, str],
    pending_responses: Dict[int, str],
    response_files: List[str]
) -> bool:
    """
    Handle AI review for a comment thread.

    Args:
        ctx: Workflow context
        pr_thread: The PR review thread (UI model)
        worktree_path: Absolute path to worktree
        pr_title: PR title for context
        comment_commits: Dict to track commits (will be updated)
        pending_responses: Dict to track responses (will be updated)
        response_files: List to track temp files (will be updated)

    Returns:
        True if processed successfully, False if failed
    """
    try:
        import json
        import os

        main_comment = pr_thread.main_comment

        # Build AI review context using operation
        review_context = build_ai_review_context(pr_thread, pr_title)

        # Store JSON context
        context_json = json.dumps(review_context, indent=2)
        ctx.data["pr_review_context"] = context_json

        # Prepare response file path for AI to save explanations
        response_file = f"/tmp/titan-ai-response-comment-{main_comment.id}.txt"
        response_files.append(response_file)

        # Clean up any existing response file
        if os.path.exists(response_file):
            os.remove(response_file)

        # Import and call ai_assistant_step
        from titan_cli.engine.steps.ai_assistant_step import execute_ai_assistant_step
        from titan_cli.core.workflows.models import WorkflowStepModel

        ai_step = WorkflowStepModel(
            id="ai_review_helper",
            plugin="core",
            step="ai_code_assistant",
            name="AI Code Review",
            params={
                "context_key": "pr_review_context",
                "prompt_template": f"""Review this PR comment thread:

```json
{{context}}
```

## Your Task

1. **First, evaluate if the review comment makes sense:**
   - Is the feedback valid and applicable to the current code?
   - Is the requested change appropriate?
   - Could previous attempts have already addressed this (check the thread conversation)?

2. **Then, based on your evaluation:**
   - **If the comment makes sense**: Make the necessary code changes to address it
   - **If the comment doesn't make sense or is outdated**:
     * DO NOT make code changes
     * Write your explanation/response EXACTLY to this file path: {response_file}
     * IMPORTANT: Use this exact command to write the response:
       ```bash
       cat > {response_file} << 'EOF'
       Your response text here
       EOF
       ```

## Response Style (CRITICAL)
- **Keep responses SHORT and CONCISE** (maximum 2-3 sentences)
- **Be direct and to the point** - no verbose explanations
- **Avoid multiple paragraphs** - use a single short paragraph
- **Don't over-explain** - state the key point clearly and move on
- Example GOOD: "This is intentional. The logic handles X at layer Y, ensuring Z."
- Example BAD: Long multi-paragraph explanations with bullet points and detailed justifications

Note: Review the entire conversation thread carefully - previous fix attempts may have failed or been incomplete.""",
                "ask_confirmation": False,
                "cli_preference": "auto"
            }
        )


        # Update project_root in context to point to worktree
        original_project_root = ctx.get("project_root", ".")

        # Verify worktree exists before changing to it
        worktree_exists = os.path.isdir(worktree_path)

        if not worktree_exists:
            ctx.textual.error_text(f"Worktree not found: {worktree_path}")
            return False

        ctx.data["project_root"] = worktree_path

        # Inform user how to return to Titan after using the AI CLI
        ctx.textual.panel(
            "When you're done using the AI CLI, press Ctrl+C twice to exit and return to Titan.",
            panel_type="warning"
        )

        # Launch AI assistant
        execute_ai_assistant_step(ai_step, ctx)

        # Restore original project_root
        ctx.data["project_root"] = original_project_root

        # Check if AI made any code changes
        ctx.textual.text("")

        status_result = ctx.git.run_in_worktree(worktree_path, ["git", "status", "--short"])
        match status_result:
            case ClientSuccess(data=status_output):
                has_changes = bool(status_output.strip())
            case ClientError():
                # AI might have provided a text response instead - check for that
                has_changes = False

        if has_changes:
            # Show what changed using diff stat inside a panel
            stat_result = ctx.git.get_worktree_diff_stat(worktree_path)
            match stat_result:
                case ClientSuccess(data=stat_output) if stat_output.strip():
                    formatted_files, formatted_summary = format_diff_stat_display(stat_output)
                    ctx.textual.show_diff_stat(formatted_files, formatted_summary, use_panel=True)
                case _:
                    ctx.textual.dim_text("Changes detected")

            # Commit immediately
            ctx.textual.text("")
            commit_msg = create_commit_message(
                main_comment.body,
                main_comment.author_login,
                main_comment.path
            )

            with ctx.textual.loading("Committing changes..."):
                commit_hash = commit_in_worktree(
                    ctx.git,
                    worktree_path,
                    commit_msg,
                    add_all=True,
                    no_verify=True
                )

            ctx.textual.success_text(f"✓ Committed: {commit_hash[:8]}")
            comment_commits[main_comment.id] = commit_hash

        else:
            # No code changes - check for text response
            ctx.textual.dim_text("No code changes were made")

            response_found_at = find_ai_response_file(main_comment.id, response_file)

            if response_found_at:
                with open(response_found_at, 'r') as f:
                    ai_response = f.read().strip()

                if response_found_at != response_file:
                    ctx.textual.dim_text(f"Found response at: {response_found_at}")

                ctx.textual.success_text("✓ AI provided a response (will review all at the end)")
                pending_responses[main_comment.id] = {"text": ai_response, "source": "ai"}
            else:
                ctx.textual.warning_text("⚠ No AI response found - AI may have skipped this comment")
                ctx.textual.dim_text(f"Searched for: {os.path.basename(response_file)}")
                return False

        return True

    except Exception as e:
        ctx.textual.error_text(f"AI review error: {e}")
        import traceback
        ctx.textual.dim_text(traceback.format_exc())
        return False


def _handle_resolve_thread(
    ctx: WorkflowContext,
    pr_thread: UICommentThread
) -> bool:
    """
    Handle resolving a review thread.

    Args:
        ctx: Workflow context
        pr_thread: The PR review thread to resolve

    Returns:
        True if resolved successfully, False if failed
    """
    thread_id = pr_thread.thread_id
    if not thread_id:
        ctx.textual.error_text("Cannot resolve thread: missing thread ID")
        return False

    with ctx.textual.loading("Resolving thread..."):
        result = ctx.github.resolve_review_thread(thread_id)

    match result:
        case ClientSuccess():
            ctx.textual.success_text("Thread resolved")
            return True
        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to resolve thread: {err}")
            return False


# ============================================================================
# WORKFLOW STEPS
# ============================================================================


def select_pr_for_review_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Select a PR from the user's open PRs to review comments.

    Outputs (saved to ctx.data):
        selected_pr_number (int): The selected PR number
        selected_pr_title (str): The selected PR title

    Returns:
        Success: PR selected successfully
        Skip: No PRs available or user cancelled
        Error: Failed to fetch PRs
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Select PR for Review")

    # Get GitHub client
    if not ctx.github:
        ctx.textual.end_step("error")
        return Error("GitHub client not available")

    # Fetch user's open PRs (returns ClientResult[List[UIPullRequest]])
    with ctx.textual.loading("Fetching your open PRs..."):
        result = ctx.github.list_my_prs(state="open")

    match result:
        case ClientSuccess(data=prs):
            if not prs:
                ctx.textual.dim_text("You don't have any open PRs.")
                ctx.textual.end_step("success")
                return Exit("No open PRs found")

            # Create options from PRs
            options = []
            for pr in prs:
                options.append(
                    OptionItem(
                        value=pr.number,
                        title=f"#{pr.number}: {pr.title}",
                        description=f"Branch: {pr.branch_info}"  # Pre-formatted "head → base"
                    )
                )

            # Ask user to select a PR
            try:
                selected = ctx.textual.ask_option(
                    f"Select a PR to review comments ({len(prs)} open PR(s)):",
                    options
                )

                if not selected:
                    ctx.textual.warning_text("No PR selected")
                    ctx.textual.end_step("skip")
                    return Exit("User cancelled PR selection")

                # selected is already the PR number (int)
                pr_number = selected
                selected_pr = next((pr for pr in prs if pr.number == pr_number), None)

                if not selected_pr:
                    ctx.textual.end_step("error")
                    return Error(f"PR #{pr_number} not found")

                # Save to context
                metadata = {
                    "selected_pr_number": pr_number,
                    "selected_pr_title": selected_pr.title,
                    "selected_pr_head_branch": selected_pr.head_ref,
                    "selected_pr_base_branch": selected_pr.base_ref,
                }

                ctx.textual.success_text(f"Selected PR #{pr_number}: {selected_pr.title}")
                ctx.textual.end_step("success")

                return Success(
                    f"Selected PR #{pr_number}",
                    metadata=metadata
                )

            except Exception as e:
                ctx.textual.error_text(f"Failed during PR selection: {e}")
                ctx.textual.end_step("error")
                return Error(str(e))

        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to fetch PRs: {err}")
            ctx.textual.end_step("error")
            return Error(f"Failed to fetch PRs: {err}")


def fetch_pending_comments_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Fetch unresolved review threads for the selected PR using GraphQL.

    Fetches structured threads (main comment + replies) that are NOT resolved.

    Requires (from ctx.data):
        selected_pr_number (int): The PR number

    Outputs (saved to ctx.data):
        review_threads (List[UICommentThread]): Unresolved review threads (UI models)

    Returns:
        Success: Threads fetched
        Skip: No unresolved threads
        Error: Failed to fetch threads
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Fetch Pending Comments")

    # Get PR number from context
    pr_number = ctx.get("selected_pr_number")
    if not pr_number:
        ctx.textual.end_step("error")
        return Error("No PR selected")

    # Get GitHub client
    if not ctx.github:
        ctx.textual.end_step("error")
        return Error("GitHub client not available")

    try:
        # Fetch and filter review threads
        with ctx.textual.loading(f"Fetching comments for PR #{pr_number}..."):
            filtered_threads = fetch_pr_threads(ctx.github, pr_number, include_resolved=False)

        if not filtered_threads:
            ctx.textual.dim_text(f"No unresolved threads found for PR #{pr_number}")
            ctx.textual.end_step("skip")
            return Exit("No unresolved threads")

        # Show summary
        ctx.textual.success_text(f"Found {len(filtered_threads)} unresolved thread(s)")
        ctx.textual.text("")

        # Save to context
        metadata = {
            "review_threads": filtered_threads,
            "total_pending": len(filtered_threads),
        }

        ctx.textual.end_step("success")

        return Success(
            f"Found {len(filtered_threads)} unresolved threads",
            metadata=metadata
        )

    except Exception as e:
        ctx.textual.error_text(f"Failed to fetch threads: {e}")
        ctx.textual.end_step("error")
        return Error(str(e))


def create_worktree_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Create worktree for PR review.

    Requires (from ctx.data):
        selected_pr_number (int): The PR number
        selected_pr_head_branch (str): Branch to checkout in worktree

    Outputs (saved to ctx.data):
        worktree_path (str): Absolute path to worktree
        worktree_created (bool): Whether worktree was created

    Returns:
        Success: Worktree created
        Error: Failed to create worktree
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Create Worktree")

    # Get data from context
    pr_number = ctx.get("selected_pr_number")
    head_branch = ctx.get("selected_pr_head_branch", "")

    if not pr_number or not head_branch:
        ctx.textual.error_text("Missing PR number or branch")
        ctx.textual.end_step("error")
        return Error("Missing required data")

    # Check if Git client is available
    if not ctx.git:
        ctx.textual.error_text("Git client not available")
        ctx.textual.end_step("error")
        return Error("Git client not available")

    # Create worktree
    ctx.textual.text("")
    with ctx.textual.loading(f"Creating worktree for PR #{pr_number}..."):
        remote = getattr(ctx.git, 'default_remote', 'origin')
        worktree_path, worktree_created = setup_worktree(
            ctx.git,
            pr_number,
            head_branch,
            remote=remote
        )

    if worktree_created:
        worktree_name = os.path.basename(worktree_path)
        ctx.textual.success_text(f"✓ Worktree created: {worktree_name}")
        ctx.textual.end_step("success")

        metadata = {
            "worktree_path": worktree_path,
            "worktree_created": True,
        }

        return Success("Worktree created", metadata=metadata)
    else:
        ctx.textual.error_text("Failed to create worktree")
        ctx.textual.end_step("error")
        return Error("Failed to create worktree")


def review_comments_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Review all unresolved comment threads one by one and take action.

    Uses GraphQL-structured threads (main comment + replies).

    Requires (from ctx.data):
        selected_pr_number (int): The PR number
        review_threads (List[UICommentThread]): Unresolved threads (UI models)
        worktree_path (str): Absolute path to worktree (from create_worktree_step)
        worktree_created (bool): Whether worktree was created (from create_worktree_step)

    Returns:
        Success: All threads processed
        Skip: User cancelled review
        Error: Failed to process threads
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Review Comments")

    try:
        # Get data from context
        pr_number = ctx.get("selected_pr_number")
        review_threads: List[UICommentThread] = ctx.get("review_threads", [])
        pr_title = ctx.get("selected_pr_title", "")

        # Get worktree info from create_worktree_step
        worktree_path = ctx.get("worktree_path")
        worktree_created = ctx.get("worktree_created", False)

        if not pr_number or not review_threads:
            ctx.textual.end_step("error")
            return Error("Missing required data")

        if not worktree_created or not worktree_path:
            ctx.textual.error_text("Worktree not available")
            ctx.textual.end_step("error")
            return Error("Worktree not available")

        # Track state
        comment_commits = {}  # {comment_id: commit_hash}
        pending_responses = {}  # {comment_id: response_text}
        response_files = []  # Track temp files for cleanup
        processed_count = 0
        skipped_count = 0

        # Loop through all review threads
        for thread_idx, pr_thread in enumerate(review_threads):
            # Show thread and get user's choice
            choice = _show_thread_and_get_action(ctx, pr_thread, thread_idx, len(review_threads))

            # Handle user choice
            if choice == "exit":
                ctx.textual.warning_text(f"Exiting review. Processed {processed_count}, skipped {skipped_count}")
                ctx.textual.end_step("success")
                return Success(
                    "Review exited early",
                    metadata={
                        "processed_count": processed_count,
                        "skipped_count": skipped_count,
                        "total_threads": len(review_threads),
                    }
                )

            elif choice == "skip":
                skipped_count += 1

            elif choice == "reply":
                if _handle_manual_reply(ctx, pr_thread, pending_responses):
                    processed_count += 1
                else:
                    skipped_count += 1

            elif choice == "ai_review":
                if not worktree_created or not worktree_path:
                    ctx.textual.error_text("Worktree not available")
                    skipped_count += 1
                    continue

                if _handle_ai_review(
                    ctx, pr_thread, worktree_path,
                    pr_title, comment_commits, pending_responses, response_files
                ):
                    processed_count += 1
                else:
                    skipped_count += 1

            elif choice == "resolve":
                if _handle_resolve_thread(ctx, pr_thread):
                    processed_count += 1
                else:
                    skipped_count += 1

        # Summary - don't send anything yet, just show what was generated
        ctx.textual.text("")
        ctx.textual.success_text(
            f"Review complete! Processed {processed_count}, skipped {skipped_count} "
            f"out of {len(review_threads)} thread(s)"
        )
        if pending_responses:
            ctx.textual.dim_text(f"  • {len(pending_responses)} response(s) ready to send")

        ctx.textual.end_step("success")

        # Store data for next steps (worktree info already in context from create_worktree_step)
        metadata = {
            "processed_count": processed_count,
            "skipped_count": skipped_count,
            "total_threads": len(review_threads),
            "comment_commits": comment_commits,  # {comment_id: commit_hash}
            "pending_responses": pending_responses,  # {comment_id: {"text": ..., "source": ...}}
        }

        return Success(
            f"Reviewed {len(review_threads)} comment thread(s)",
            metadata=metadata
        )

    except Exception as e:
        import traceback
        error_msg = f"Error in review_comments_step: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.text("")
        ctx.textual.dim_text(traceback.format_exc())
        ctx.textual.end_step("error")
        return Error(error_msg)

    finally:
        # Cleanup temporary AI response files
        if response_files:
            for response_file in response_files:
                try:
                    if os.path.exists(response_file):
                        os.remove(response_file)
                except Exception:
                    pass
        # Note: Worktree cleanup moved to cleanup_worktree_step (runs after push)


def push_commits_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Push commits to PR branch.

    Requires (from ctx.data):
        selected_pr_number (int): The PR number
        selected_pr_head_branch (str): Branch to push to
        comment_commits (Dict[int, str]): Map of comment_id -> commit_hash
        worktree_path (str): Absolute path to worktree
        worktree_created (bool): Whether worktree was created

    Outputs (saved to ctx.data):
        push_successful (bool): Whether push succeeded

    Returns:
        Success: Commits pushed
        Skip: No commits to push or user cancelled
        Error: Failed to push
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Push Commits")

    # Get data from context
    head_branch = ctx.get("selected_pr_head_branch", "")
    comment_commits = ctx.get("comment_commits", {})
    worktree_path = ctx.get("worktree_path")
    worktree_created = ctx.get("worktree_created", False)

    # Check if Git client is available
    if not ctx.git:
        ctx.textual.error_text("Git client not available")
        ctx.textual.end_step("error")
        return Error("Git client not available")

    # Check if there are commits to push
    if not comment_commits:
        ctx.textual.dim_text("No commits to push")
        ctx.textual.end_step("skip")
        return Skip("No commits to push")

    if not worktree_created or not worktree_path:
        ctx.textual.error_text("Worktree not available")
        ctx.textual.end_step("error")
        return Error("Worktree not available")

    # Show commits to push
    ctx.textual.text("")

    # List commits using service method
    commits_result = ctx.git.get_commits(worktree_path, limit=len(comment_commits))
    match commits_result:
        case ClientSuccess(data=commits):
            ctx.textual.bold_text(f"Push {len(commits)} commit(s) to `{head_branch}`")
            for c in commits:
                ctx.textual.text(f"  - {c.short_hash} {c.message_subject}")
        case ClientError():
            ctx.textual.bold_text(f"Push {len(comment_commits)} commit(s) to {head_branch}")

    ctx.textual.text("")

    # Ask confirmation
    should_push = ctx.textual.ask_confirm(
        "Do you want to push these commit(s) to the PR branch?",
        default=True
    )

    if not should_push:
        ctx.textual.dim_text("Push cancelled")
        ctx.textual.end_step("skip")
        return Skip("Push cancelled by user", metadata={"push_successful": False})

    # Push
    ctx.textual.text("")

    with ctx.textual.loading(f"Pushing to {head_branch}..."):
        push_result = ctx.git.push_from_worktree(worktree_path, head_branch)

    match push_result:
        case ClientSuccess():
            ctx.textual.success_text(f"✓ Pushed {len(comment_commits)} commit(s) to {head_branch}")
            ctx.textual.end_step("success")
            return Success(
                f"Pushed {len(comment_commits)} commits",
                metadata={"push_successful": True}
            )
        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to push: {err}")
            ctx.textual.end_step("error")
            return Error(f"Failed to push: {err}", metadata={"push_successful": False})


def send_comment_replies_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Send comment replies (both text responses and commit hashes).

    Requires (from ctx.data):
        selected_pr_number (int): The PR number
        comment_commits (Dict[int, str]): Map of comment_id -> commit_hash
        pending_responses (Dict[int, Dict]): Map of comment_id -> {"text": ..., "source": ...}
        push_successful (bool): Whether push succeeded

    Returns:
        Success: Replies sent
        Skip: No replies to send or user cancelled
        Error: Failed to send replies
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Send Comment Replies")

    # Get data from context
    pr_number = ctx.get("selected_pr_number")
    comment_commits = ctx.get("comment_commits", {})
    pending_responses = ctx.get("pending_responses", {})
    push_successful = ctx.get("push_successful", False)

    # Prepare replies using operation (handles push failure logic)
    replies_to_send = prepare_replies_for_sending(
        pending_responses,
        comment_commits,
        push_successful
    )

    # Check if there's anything to send
    if not replies_to_send:
        ctx.textual.dim_text("No replies to send")
        ctx.textual.end_step("skip")
        return Skip("No replies to send")

    # Build thread lookup for context display
    review_threads: List[UICommentThread] = ctx.get("review_threads", [])
    thread_by_id = {}
    for thread in review_threads:
        if thread.main_comment:
            thread_by_id[thread.main_comment.id] = thread

    # Let user review, edit, or skip each reply before sending
    final_replies = {}
    total = len(replies_to_send)

    for i, (comment_id, reply_text) in enumerate(replies_to_send.items(), 1):
        ctx.textual.text("")

        # Show context
        thread = thread_by_id.get(comment_id)
        if thread and thread.main_comment:
            mc = thread.main_comment
            filename = mc.path.split('/')[-1] if mc.path else "General"
            ctx.textual.dim_text(f"Reply {i}/{total} — {mc.author_login} on {filename}")
        else:
            ctx.textual.dim_text(f"Reply {i}/{total}")

        for line in reply_text.splitlines():
            ctx.textual.text(f"  {line}")

        choice = ctx.textual.ask_choice(
            "What would you like to do?",
            options=[
                ChoiceOption(value="send", label="Send", variant="primary"),
                ChoiceOption(value="edit", label="Edit", variant="default"),
                ChoiceOption(value="skip", label="Skip", variant="error"),
            ]
        )

        if choice == "send":
            final_replies[comment_id] = reply_text
        elif choice == "edit":
            edited = ctx.textual.ask_multiline("Edit reply:", default=reply_text)
            if edited and edited.strip():
                final_replies[comment_id] = edited.strip()
            else:
                ctx.textual.dim_text("Empty reply, skipping")

    if not final_replies:
        ctx.textual.dim_text("All replies skipped")
        ctx.textual.end_step("skip")
        return Skip("All replies skipped")

    # Send confirmed replies
    with ctx.textual.loading(f"Sending {len(final_replies)} reply(s)..."):
        results = reply_to_comment_batch(ctx.github, pr_number, final_replies)

    replied_count = sum(results.values())
    failed_count = len(results) - replied_count

    if replied_count > 0:
        ctx.textual.success_text(f"✓ Sent {replied_count} reply(s)")
    if failed_count > 0:
        ctx.textual.warning_text(f"⚠ Failed to send {failed_count} reply(s)")

    ctx.textual.end_step("success")

    return Success(
        f"Sent {replied_count} replies",
        metadata={"replies_sent": replied_count, "replies_failed": failed_count}
    )


def request_review_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Re-request review from existing reviewers.

    Requires (from ctx.data):
        selected_pr_number (int): The PR number
        push_successful (bool): Whether push succeeded

    Returns:
        Success: Review re-requested
        Skip: Push didn't succeed or user cancelled
        Error: Failed to request review
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Review Requested")

    # Get data from context
    pr_number = ctx.get("selected_pr_number")
    push_successful = ctx.get("push_successful", False)

    # Only re-request if push succeeded
    if not push_successful:
        ctx.textual.dim_text("Skipping re-request (no commits were pushed)")
        ctx.textual.end_step("skip")
        return Skip("No commits pushed")

    # Ask confirmation
    ctx.textual.text("")
    should_rerequest = ctx.textual.ask_confirm(
        "Do you want to re-request review from existing reviewers?",
        default=True
    )

    if not should_rerequest:
        ctx.textual.dim_text("Re-request cancelled")
        ctx.textual.end_step("skip")
        return Skip("Re-request cancelled by user")

    # Re-request review
    with ctx.textual.loading("Re-requesting review..."):
        result = ctx.github.request_pr_review(pr_number)

    match result:
        case ClientSuccess(message=msg):
            ctx.textual.success_text(f"✓ {msg}")
            ctx.textual.end_step("success")
            return Success("Review re-requested")
        case ClientError(error_message=err):
            ctx.textual.warning_text(f"Re-request partially failed: {err}")
            ctx.textual.dim_text("Some reviewers may have been skipped (e.g., bots)")
            ctx.textual.end_step("success")  # Still success - partial is OK
            return Success("Review re-requested (partial)")


def cleanup_worktree_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Cleanup worktree created for PR review.

    Requires (from ctx.data):
        worktree_created (bool): Whether worktree was created
        worktree_path (str): Absolute path to worktree

    Returns:
        Success: Worktree cleaned up
        Skip: No worktree to cleanup
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Cleanup Worktree")

    # Get data from context
    worktree_created = ctx.get("worktree_created", False)
    worktree_path = ctx.get("worktree_path")

    # Check if worktree needs cleanup
    if not worktree_created or not worktree_path:
        ctx.textual.dim_text("No worktree to cleanup")
        ctx.textual.end_step("skip")
        return Exit("No worktree to cleanup")

    # Check if Git client is available
    if not ctx.git:
        ctx.textual.warning_text("Git client not available - cannot cleanup")
        ctx.textual.end_step("skip")
        return Exit("Git client not available")

    # Cleanup worktree
    with ctx.textual.loading("Cleaning up worktree..."):
        success = cleanup_worktree(ctx.git, worktree_path)

    if success:
        ctx.textual.success_text("✓ Worktree cleaned up")
        ctx.textual.end_step("success")
        return Success("Worktree cleaned up")
    else:
        ctx.textual.warning_text("Failed to cleanup worktree")
        ctx.textual.end_step("skip")
        return Exit("Cleanup failed")


# Export for plugin registration
__all__ = [
    "select_pr_for_review_step",
    "fetch_pending_comments_step",
    "create_worktree_step",
    "review_comments_step",
    "push_commits_step",
    "send_comment_replies_step",
    "request_review_step",
    "cleanup_worktree_step",
]
