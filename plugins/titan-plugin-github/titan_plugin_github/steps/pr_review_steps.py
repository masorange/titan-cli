"""
Steps for reviewing and addressing PR comments.

This module contains steps for reviewing PR comments and UI helpers
to keep the main step functions clean and readable.
"""
import os
import threading
from typing import List, Dict
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Exit
from titan_cli.ui.tui.widgets import ChoiceOption, OptionItem
from titan_plugin_github.widgets import CommentThread
from ..models import UICommentThread
from ..models.network.graphql import GraphQLPullRequestReviewThread
from ..operations import (
    fetch_pr_threads,
    setup_worktree,
    cleanup_worktree,
    commit_in_worktree,
    push_and_request_review,
    build_ai_review_context,
    detect_worktree_changes,
    find_ai_response_file,
    create_commit_message,
    reply_to_comment_batch,
)


# ============================================================================
# UI HELPER FUNCTIONS (Private)
# ============================================================================


def _show_thread_and_get_action(
    ctx: WorkflowContext,
    pr_thread: GraphQLPullRequestReviewThread,
    thread_idx: int,
    total_threads: int
) -> str:
    """
    Display a comment thread and get user's action choice.

    Args:
        ctx: Workflow context
        pr_thread: The PR review thread to display
        thread_idx: Current thread index (0-based)
        total_threads: Total number of threads

    Returns:
        User's choice: "ai_review", "reply", "skip", "resolve", or "exit"
    """
    # Convert GraphQLPullRequestReviewThread to UICommentThread
    ui_thread = UICommentThread.from_review_thread(pr_thread)

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
        thread=ui_thread,
        thread_number=f"Thread {thread_idx + 1} of {total_threads}",
        options=options,
        on_select=on_choice_selected
    )

    ctx.textual.text("")
    ctx.textual.mount(thread_widget)

    # Wait for user selection
    result_event.wait()
    choice = result_container.get("choice")

    # Replace the choice buttons with selected action text
    def replace_buttons_with_text():
        from titan_cli.ui.tui.widgets import PromptChoice, DimText
        try:
            prompt_widget = thread_widget.query_one(PromptChoice)
            prompt_widget.remove()

            action_labels = {
                "ai_review": "Launching AI to review and fix",
                "reply": "Replying manually",
                "skip": "Skipped",
                "resolve": "Resolving thread",
                "exit": "Exiting review"
            }
            label = action_labels.get(choice, f"Action: {choice}")
            thread_widget.mount(DimText(f"→ {label}"))
        except Exception:
            pass

    ctx.textual.app.call_from_thread(replace_buttons_with_text)

    return choice


def _handle_manual_reply(
    ctx: WorkflowContext,
    pr_thread: GraphQLPullRequestReviewThread,
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
        pending_responses[main_comment_id] = reply_text
        ctx.textual.success_text("✓ Reply queued for review")
        return True
    else:
        ctx.textual.warning_text("Empty reply, skipping")
        return False


def _handle_ai_review(
    ctx: WorkflowContext,
    pr_thread: GraphQLPullRequestReviewThread,
    worktree_path: str,
    full_worktree_path: str,
    pr_title: str,
    comment_commits: Dict[int, str],
    pending_responses: Dict[int, str],
    response_files: List[str]
) -> bool:
    """
    Handle AI review for a comment thread.

    Args:
        ctx: Workflow context
        pr_thread: The PR review thread
        worktree_path: Relative path to worktree
        full_worktree_path: Absolute path to worktree
        pr_title: PR title for context
        comment_commits: Dict to track commits (will be updated)
        pending_responses: Dict to track responses (will be updated)
        response_files: List to track temp files (will be updated)

    Returns:
        True if processed successfully, False if failed
    """
    try:
        import json

        main_comment = pr_thread.main_comment

        # Build AI review context using operation
        review_context = build_ai_review_context(pr_thread, pr_title)

        # Store JSON context
        ctx.data["pr_review_context"] = json.dumps(review_context, indent=2)

        # Take snapshot of current worktree state BEFORE AI review
        status_before = ctx.git.run_in_worktree(worktree_path, ["git", "status", "--short"])

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
{{{{context}}}}
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
     * The response should be a professional reply to the reviewer explaining why the comment doesn't apply

Note: Review the entire conversation thread carefully - previous fix attempts may have failed or been incomplete.""",
                "ask_confirmation": False,
                "cli_preference": "auto"
            }
        )

        # Update project_root in context to point to worktree
        original_project_root = ctx.get("project_root", ".")
        ctx.data["project_root"] = full_worktree_path

        # Launch AI assistant
        execute_ai_assistant_step(ai_step, ctx)

        # Restore original project_root
        ctx.data["project_root"] = original_project_root

        # Check if there are NEW changes after AI work
        ctx.textual.text("")
        status_after = ctx.git.run_in_worktree(worktree_path, ["git", "status", "--short"])

        # Detect NEW changes using operation
        has_new_changes, new_changes = detect_worktree_changes(status_before, status_after)

        if has_new_changes:
            # Show what changed
            changed_files = list(new_changes)
            ctx.textual.success_text(f"✓ New changes detected: {len(changed_files)} file(s)")
            for file_change in changed_files[:5]:
                ctx.textual.dim_text(f"  {file_change}")
            if len(changed_files) > 5:
                ctx.textual.dim_text(f"  ... and {len(changed_files) - 5} more")

            # Commit immediately
            ctx.textual.text("")
            commit_msg = create_commit_message(
                main_comment.body,
                main_comment.author.login,
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
                pending_responses[main_comment.id] = ai_response
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
    pr_thread: GraphQLPullRequestReviewThread
) -> bool:
    """
    Handle resolving a review thread.

    Args:
        ctx: Workflow context
        pr_thread: The PR review thread to resolve

    Returns:
        True if resolved successfully, False if failed
    """
    try:
        thread_id = pr_thread.id
        if not thread_id:
            ctx.textual.error_text("Cannot resolve thread: missing thread ID")
            return False

        with ctx.textual.loading("Resolving thread..."):
            ctx.github.resolve_review_thread(thread_id)

        ctx.textual.success_text("Thread resolved")
        return True

    except Exception as e:
        ctx.textual.error_text(f"Failed to resolve thread: {e}")
        return False


def _review_and_send_responses(
    ctx: WorkflowContext,
    pr_number: int,
    pending_responses: Dict[int, str],
    review_threads: List[GraphQLPullRequestReviewThread]
) -> None:
    """
    Review AI responses with user and send approved ones.

    Args:
        ctx: Workflow context
        pr_number: PR number
        pending_responses: Dict of comment_id -> response_text
        review_threads: All review threads (for mapping comment IDs)
    """
    if not pending_responses:
        return

    ctx.textual.text("")
    ctx.textual.text("")
    ctx.textual.bold_text(f"=== AI Responses Review ({len(pending_responses)} response(s)) ===")
    ctx.textual.text("")

    # Map comment IDs to thread info
    comment_map = {thread.main_comment.id: thread for thread in review_threads}

    # Show each response and allow editing
    responses_to_send = {}

    for comment_id, ai_response in pending_responses.items():
        thread = comment_map.get(comment_id)
        if not thread:
            continue

        main_comment = thread.main_comment
        ctx.textual.text("")
        ctx.textual.primary_text(f"Comment by {main_comment.author.login} on {main_comment.path or 'PR'}:")
        ctx.textual.dim_text(f"  {main_comment.body[:100]}..." if len(main_comment.body) > 100 else f"  {main_comment.body}")
        ctx.textual.text("")
        ctx.textual.bold_text("AI Response:")
        ctx.textual.markdown(ai_response)
        ctx.textual.text("")

        # Ask what to do with this response
        response_options = [
            ChoiceOption(value="use", label="Use as-is", variant="primary"),
            ChoiceOption(value="edit", label="Edit", variant="default"),
            ChoiceOption(value="skip", label="Skip", variant="default"),
        ]

        response_action = ctx.textual.ask_choice(
            "What would you like to do with this response?",
            response_options
        )

        if response_action == "use":
            responses_to_send[comment_id] = ai_response
        elif response_action == "edit":
            ctx.textual.text("")
            edited_response = ctx.textual.ask_multiline(
                "Edit the response:",
                default=ai_response
            )
            if edited_response and edited_response.strip():
                responses_to_send[comment_id] = edited_response
            else:
                ctx.textual.warning_text("Empty response, skipping")

    # Send all approved responses
    if responses_to_send:
        ctx.textual.text("")
        with ctx.textual.loading(f"Sending {len(responses_to_send)} response(s)..."):
            results = reply_to_comment_batch(ctx.github, pr_number, responses_to_send)

        replied_count = sum(results.values())
        failed_count = len(results) - replied_count

        ctx.textual.success_text(f"✓ Sent {replied_count} response(s)")
        if failed_count > 0:
            ctx.textual.warning_text(f"⚠ Failed to send {failed_count} response(s)")
    else:
        ctx.textual.dim_text("No responses to send")


def _send_commit_auto_replies(
    ctx: WorkflowContext,
    pr_number: int,
    comment_commits: Dict[int, str]
) -> None:
    """
    Send auto-replies for commits with "Fixed in {hash}" message.

    Args:
        ctx: Workflow context
        pr_number: PR number
        comment_commits: Dict of comment_id -> commit_hash
    """
    if not comment_commits:
        return

    ctx.textual.text("")
    ctx.textual.text("")
    ctx.textual.bold_text(f"=== Auto-reply to Code Changes ({len(comment_commits)} comment(s)) ===")
    ctx.textual.text("")

    should_reply = ctx.textual.ask_confirm(
        f"Do you want to reply to {len(comment_commits)} comment(s) with their commit hashes?",
        default=True
    )

    if should_reply:
        ctx.textual.text("")

        # Build replies dict
        auto_replies = {
            comment_id: f"Fixed in {commit_hash[:8]}"
            for comment_id, commit_hash in comment_commits.items()
        }

        # Send batch
        with ctx.textual.loading(f"Sending {len(auto_replies)} auto-reply(s)..."):
            results = reply_to_comment_batch(ctx.github, pr_number, auto_replies)

        replied_count = sum(results.values())
        failed_count = len(results) - replied_count

        # Show individual results
        for comment_id, success in results.items():
            if success:
                ctx.textual.dim_text(f"  ✓ Replied with: Fixed in {comment_commits[comment_id][:8]}")
            else:
                ctx.textual.warning_text(f"  ✗ Failed to reply to comment {comment_id}")

        ctx.textual.success_text(f"✓ Sent {replied_count} auto-reply(s)")
        if failed_count > 0:
            ctx.textual.warning_text(f"⚠ Failed to send {failed_count} auto-reply(s)")
    else:
        ctx.textual.dim_text("Skipped auto-replies")


def _push_commits_to_pr(
    ctx: WorkflowContext,
    pr_number: int,
    head_branch: str,
    worktree_path: str,
    commit_count: int
) -> None:
    """
    Push commits to PR branch and optionally re-request review.

    Args:
        ctx: Workflow context
        pr_number: PR number
        head_branch: Branch to push to
        worktree_path: Path to worktree
        commit_count: Number of commits to push
    """
    ctx.textual.text("")
    ctx.textual.text("")
    ctx.textual.bold_text(f"=== Push Changes to PR ({commit_count} commit(s)) ===")
    ctx.textual.text("")

    should_push = ctx.textual.ask_confirm(
        f"Do you want to push {commit_count} commit(s) to the PR branch?",
        default=True
    )

    if not should_push:
        ctx.textual.dim_text("Skipped push (commits remain in worktree)")
        return

    # Ask if want to re-request review
    ctx.textual.text("")
    should_rerequest = ctx.textual.ask_confirm(
        "Do you want to re-request review from existing reviewers?",
        default=True
    )

    # Push and optionally re-request review
    ctx.textual.text("")
    with ctx.textual.loading(f"Pushing to {head_branch}..."):
        if should_rerequest:
            success = push_and_request_review(
                ctx.github,
                ctx.git,
                worktree_path,
                head_branch,
                pr_number
            )
        else:
            # Just push without re-requesting
            try:
                ctx.git.run_in_worktree(worktree_path, ["git", "push", "origin", head_branch])
                success = True
            except Exception:
                success = False

    if success:
        ctx.textual.success_text(f"✓ Pushed to {head_branch}")
        if should_rerequest:
            ctx.textual.success_text("✓ Review re-requested from existing reviewers")
    else:
        ctx.textual.error_text("Failed to push or re-request review")


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

    try:
        # Fetch user's open PRs (returns List[UIPullRequest])
        with ctx.textual.loading("Fetching your open PRs..."):
            prs = ctx.github.list_my_prs(state="open")

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
        ctx.textual.error_text(f"Failed to fetch PRs: {e}")
        ctx.textual.end_step("error")
        return Error(str(e))


def fetch_pending_comments_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Fetch unresolved review threads for the selected PR using GraphQL.

    Fetches structured threads (main comment + replies) that are NOT resolved.

    Requires (from ctx.data):
        selected_pr_number (int): The PR number

    Outputs (saved to ctx.data):
        review_threads (List[GraphQLPullRequestReviewThread]): Unresolved review threads

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


def review_comments_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Review all unresolved comment threads one by one and take action.

    Uses GraphQL-structured threads (main comment + replies).

    Requires (from ctx.data):
        selected_pr_number (int): The PR number
        review_threads (List[GraphQLPullRequestReviewThread]): Unresolved threads from GraphQL

    Returns:
        Success: All threads processed
        Skip: User cancelled review
        Error: Failed to process threads
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Review Comments")

    worktree_path = None
    worktree_created = False

    try:
        # Get data from context
        pr_number = ctx.get("selected_pr_number")
        review_threads: List[GraphQLPullRequestReviewThread] = ctx.get("review_threads", [])
        head_branch = ctx.get("selected_pr_head_branch", "")
        pr_title = ctx.get("selected_pr_title", "")

        if not pr_number or not review_threads:
            ctx.textual.end_step("error")
            return Error("Missing required data")

        # Create worktree once for all AI reviews
        if ctx.git:
            ctx.textual.text("")
            with ctx.textual.loading(f"Creating worktree for PR #{pr_number}..."):
                worktree_path, full_worktree_path, worktree_created = setup_worktree(
                    ctx.git,
                    pr_number,
                    head_branch
                )

            if worktree_created:
                ctx.textual.success_text(f"Worktree created at {worktree_path}")
            else:
                ctx.textual.error_text("Failed to create worktree")
                ctx.textual.end_step("error")
                return Error("Failed to create worktree")
        else:
            worktree_path = None
            full_worktree_path = None
            worktree_created = False

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
                if not worktree_created or not full_worktree_path:
                    ctx.textual.error_text("Worktree not available")
                    skipped_count += 1
                    continue

                if _handle_ai_review(
                    ctx, pr_thread, worktree_path, full_worktree_path,
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

        # Review and send AI responses
        _review_and_send_responses(ctx, pr_number, pending_responses, review_threads)

        # Send auto-replies for commits
        _send_commit_auto_replies(ctx, pr_number, comment_commits)

        # Push commits and re-request review
        if comment_commits and worktree_created and worktree_path:
            _push_commits_to_pr(ctx, pr_number, head_branch, worktree_path, len(comment_commits))

        # Summary
        ctx.textual.text("")
        ctx.textual.success_text(
            f"Review complete! Processed {processed_count}, skipped {skipped_count} "
            f"out of {len(review_threads)} thread(s)"
        )
        if comment_commits:
            ctx.textual.dim_text(f"  • {len(comment_commits)} commit(s) created")
        if pending_responses:
            ctx.textual.dim_text(f"  • {len(pending_responses)} text response(s) sent")

        ctx.textual.end_step("success")

        return Success(
            f"Reviewed {len(review_threads)} comment thread(s)",
            metadata={
                "processed_count": processed_count,
                "skipped_count": skipped_count,
                "total_threads": len(review_threads),
                "commits_created": len(comment_commits),
                "text_responses_sent": len(pending_responses),
            }
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

        # Cleanup worktree if it was created
        if worktree_created and worktree_path and ctx.git:
            with ctx.textual.loading("Cleaning up worktree..."):
                success = cleanup_worktree(ctx.git, worktree_path)

            if success:
                ctx.textual.dim_text("Worktree cleaned up")
            else:
                ctx.textual.warning_text("Failed to cleanup worktree")


# Export for plugin registration
__all__ = [
    "select_pr_for_review_step",
    "fetch_pending_comments_step",
    "review_comments_step",
]
