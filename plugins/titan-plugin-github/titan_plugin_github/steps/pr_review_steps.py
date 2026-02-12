"""
Steps for reviewing and addressing PR comments.
"""
import threading
from typing import List
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip, Exit
from titan_cli.ui.tui.widgets import ChoiceOption, OptionItem
from titan_plugin_github.widgets import CommentThread
from titan_cli.ui.tui.models import UICommentThread
from ..models import PRReviewThread


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
        # Fetch user's open PRs
        with ctx.textual.loading("Fetching your open PRs..."):
            result = ctx.github.list_my_prs(state="open")

        if not result.prs:
            ctx.textual.dim_text("You don't have any open PRs.")
            ctx.textual.end_step("success")
            return Exit("No open PRs found")

        # Create options from PRs
        options = []
        for pr in result.prs:
            options.append(
                OptionItem(
                    value=pr.number,
                    title=f"#{pr.number}: {pr.title}",
                    description=f"Branch: {pr.head_ref} → {pr.base_ref}"
                )
            )

        # Ask user to select a PR
        selected = ctx.textual.ask_option(
            f"Select a PR to review comments ({result.total} open PR(s)):",
            options
        )

        if not selected:
            ctx.textual.warning_text("No PR selected")
            ctx.textual.end_step("skip")
            return Exit("User cancelled PR selection")

        # selected is already the PR number (int)
        pr_number = selected
        selected_pr = next((pr for pr in result.prs if pr.number == pr_number), None)

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
        review_threads (List[PRReviewThread]): Unresolved review threads

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
        # Fetch review threads using GraphQL (exclude resolved threads)
        with ctx.textual.loading(f"Fetching comments for PR #{pr_number}..."):
            all_threads = ctx.github.get_pr_review_threads(pr_number, include_resolved=False)

        # Filter out bot comments and empty threads
        filtered_threads = []
        for thread in all_threads:
            main_comment = thread.main_comment
            if not main_comment:
                continue

            # Skip bot comments
            if main_comment.author and 'bot' in main_comment.author.login.lower():
                continue

            # Skip empty comments
            if not main_comment.body or not main_comment.body.strip():
                continue

            # Skip JSON-only comments (coverage reports, etc.)
            body_stripped = main_comment.body.strip()
            if body_stripped.startswith('{') and body_stripped.endswith('}'):
                continue

            filtered_threads.append(thread)

        if not filtered_threads:
            ctx.textual.dim_text(f"No unresolved threads found for PR #{pr_number}")
            ctx.textual.end_step("skip")
            return Exit("No unresolved threads")

        # Show summary
        ctx.textual.success_text(f"Found {len(filtered_threads)} unresolved thread(s)")
        ctx.textual.text("")

        # Save to context
        metadata = {
            "review_threads": filtered_threads,  # Structured threads from GraphQL
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
        review_threads (List[PRReviewThread]): Unresolved threads from GraphQL

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
        review_threads: List[PRReviewThread] = ctx.get("review_threads", [])
        head_branch = ctx.get("selected_pr_head_branch", "")

        if not pr_number or not review_threads:
            ctx.textual.end_step("error")
            return Error("Missing required data")

        if not review_threads:
            ctx.textual.dim_text("No pending comment threads")
            ctx.textual.end_step("skip")
            return Skip("No pending threads")

        # Create worktree once for all AI reviews
        if ctx.git:
            import os
            worktree_name = f"titan-review-{pr_number}"
            worktree_path = f".titan/worktrees/{worktree_name}"
            original_cwd = os.getcwd()
            full_worktree_path = os.path.join(original_cwd, worktree_path)

            ctx.textual.text("")
            with ctx.textual.loading(f"Creating worktree for PR #{pr_number}..."):
                # Remove worktree if it already exists
                try:
                    ctx.git.remove_worktree(worktree_path, force=True)
                except Exception:
                    pass

                # Create new worktree from head branch
                ctx.git.create_worktree(
                    path=worktree_path,
                    branch=head_branch,
                    create_branch=False
                )
                worktree_created = True

            ctx.textual.success_text(f"Worktree created at {worktree_path}")
        else:
            worktree_path = None
            full_worktree_path = None

        # Track commits made for each comment (for auto-reply)
        comment_commits = {}  # {comment_id: commit_hash}

        # Accumulate AI responses (when no code changes made)
        pending_responses = {}  # {comment_id: response_text}
        response_files = []  # Track temp files for cleanup

        # Loop through all review threads
        processed_count = 0
        skipped_count = 0

        for thread_idx, pr_thread in enumerate(review_threads):
            # Convert PRReviewThread to UICommentThread
            ui_thread = UICommentThread.from_review_thread(pr_thread)

            # Prepare action options
            options = [
                ChoiceOption(value="ai_review", label="AI Review & Fix", variant="primary"),
                ChoiceOption(value="reply", label="Reply manually", variant="default"),
                ChoiceOption(value="skip", label="Skip for now", variant="default"),
                ChoiceOption(value="resolve", label="Resolve thread", variant="success"),
            ]

            # Add "Exit" option if not the last thread
            if thread_idx < len(review_threads) - 1:
                options.append(
                    ChoiceOption(value="exit", label="Exit review", variant="error")
                )

            # Result container for callback
            result_container = {}
            result_event = threading.Event()

            def on_choice_selected(value):
                result_container["choice"] = value
                result_event.set()

            # Create and mount CommentThread widget with UICommentThread
            thread_widget = CommentThread(
                thread=ui_thread,
                thread_number=f"Thread {thread_idx + 1} of {len(review_threads)}",
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
                    # Find and remove the PromptChoice widget
                    prompt_widget = thread_widget.query_one(PromptChoice)
                    prompt_widget.remove()

                    # Add text showing selected action
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
                    pass  # Widget might not have PromptChoice

            ctx.textual.app.call_from_thread(replace_buttons_with_text)

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

            if choice == "skip":
                skipped_count += 1
                continue

            elif choice == "reply":
                # Manual reply - add to pending responses for review at the end
                ctx.textual.text("")
                reply_text = ctx.textual.ask_multiline(
                    "Enter your reply:",
                    default=""
                )

                if reply_text and reply_text.strip():
                    # Add to pending responses (will be reviewed at the end)
                    main_comment_id = pr_thread.main_comment.id
                    pending_responses[main_comment_id] = reply_text
                    ctx.textual.success_text("✓ Reply queued for review")
                    processed_count += 1
                else:
                    ctx.textual.warning_text("Empty reply, skipping")
                    skipped_count += 1

            elif choice == "ai_review":
                # AI Review & Fix - Launch AI CLI in shared worktree
                if not worktree_created or not full_worktree_path:
                    ctx.textual.error_text("Worktree not available")
                    skipped_count += 1
                    continue

                try:
                    import json
                    from ..widgets.comment_utils import extract_diff_context

                    main_comment = pr_thread.main_comment
                    pr_title = ctx.get("selected_pr_title", "")

                    # Take snapshot of current worktree state BEFORE AI review
                    status_before = ctx.git.run_in_worktree(worktree_path, ["git", "status", "--short"])
                    files_before = set(line.strip() for line in status_before.splitlines() if line.strip())

                    # Extract only relevant lines from diff_hunk (7 before + target + 3 after)
                    # This reduces token usage significantly (e.g., 200 lines → 11 lines)
                    diff_context = extract_diff_context(
                        diff_hunk=main_comment.diff_hunk,
                        target_line=main_comment.line,
                        is_outdated=False
                    ) if main_comment.diff_hunk else None

                    # Build structured JSON context (efficient, less tokens than markdown)
                    review_context = {
                        "pr": pr_title,
                        "file": main_comment.path or "N/A",
                        "line": main_comment.line,
                        "diff_hunk": diff_context,  # Use extracted context, not full diff
                        "thread": [
                            {
                                "author": main_comment.author.login,
                                "date": main_comment.created_at[:10],
                                "body": main_comment.body
                            }
                        ]
                    }

                    # Add all replies to show full conversation
                    if pr_thread.replies:
                        for reply in pr_thread.replies:
                            review_context["thread"].append({
                                "author": reply.author.login,
                                "date": reply.created_at[:10],
                                "body": reply.body
                            })

                    # Store JSON context
                    ctx.data["pr_review_context"] = json.dumps(review_context, indent=2)

                    # Prepare response file path for AI to save explanations
                    response_file = f"/tmp/titan-ai-response-comment-{main_comment.id}.txt"
                    response_files.append(response_file)  # Track for cleanup

                    # Clean up any existing response file
                    if os.path.exists(response_file):
                        os.remove(response_file)

                    # Import and call ai_assistant_step (reuse existing generic step)
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
                    ai_result = execute_ai_assistant_step(ai_step, ctx)

                    # Restore original project_root
                    ctx.data["project_root"] = original_project_root

                    # Check if there are NEW changes after AI work (compare with snapshot)
                    ctx.textual.text("")
                    status_after = ctx.git.run_in_worktree(worktree_path, ["git", "status", "--short"])
                    files_after = set(line.strip() for line in status_after.splitlines() if line.strip())

                    # Detect NEW changes (files that weren't in the before snapshot)
                    new_changes = files_after - files_before
                    has_new_changes = bool(new_changes)

                    if has_new_changes:
                        # Show what changed (only NEW changes)
                        changed_files = list(new_changes)

                        ctx.textual.success_text(f"✓ New changes detected: {len(changed_files)} file(s)")
                        for file_change in changed_files[:5]:  # Show first 5 files
                            ctx.textual.dim_text(f"  {file_change}")
                        if len(changed_files) > 5:
                            ctx.textual.dim_text(f"  ... and {len(changed_files) - 5} more")

                        # Commit immediately with a descriptive message
                        ctx.textual.text("")
                        try:
                            # Create commit message
                            comment_summary = main_comment.body[:80].replace('\n', ' ')
                            commit_msg = f"Fix PR comment: {comment_summary}\n\nComment by {main_comment.author.login} on {main_comment.path or 'PR'}"

                            # Commit changes in worktree (skip pre-commit hooks for speed and compatibility)
                            with ctx.textual.loading("Committing changes..."):
                                ctx.git.run_in_worktree(worktree_path, ["git", "add", "--all"])
                                ctx.git.run_in_worktree(worktree_path, ["git", "commit", "--no-verify", "-m", commit_msg])
                                commit_hash = ctx.git.run_in_worktree(worktree_path, ["git", "rev-parse", "HEAD"]).strip()

                            ctx.textual.success_text(f"✓ Committed: {commit_hash[:8]}")

                            # Track commit for this comment
                            comment_commits[main_comment.id] = commit_hash
                            processed_count += 1

                        except Exception as e:
                            ctx.textual.error_text(f"Failed to commit changes: {e}")
                            import traceback
                            ctx.textual.dim_text(traceback.format_exc()[:200])
                            # Still count as processed since AI did make changes
                            processed_count += 1
                    else:
                        # No code changes - check if AI left a response
                        ctx.textual.dim_text("No code changes were made")

                        # Try to read AI response from file
                        ai_response = None
                        response_found_at = None

                        # First, try the expected location
                        if os.path.exists(response_file):
                            try:
                                with open(response_file, 'r') as f:
                                    ai_response = f.read().strip()
                                response_found_at = response_file
                            except Exception as e:
                                ctx.textual.dim_text(f"Could not read AI response from {response_file}: {e}")

                        # If not found, search in common AI CLI temp directories
                        if not ai_response:
                            import glob
                            search_patterns = [
                                f"/tmp/**/titan-ai-response-comment-{main_comment.id}.txt",
                                os.path.expanduser(f"~/.gemini/tmp/**/titan-ai-response-comment-{main_comment.id}.txt"),
                                os.path.expanduser(f"~/.claude/tmp/**/titan-ai-response-comment-{main_comment.id}.txt"),
                            ]

                            for pattern in search_patterns:
                                matches = glob.glob(pattern, recursive=True)
                                if matches:
                                    try:
                                        with open(matches[0], 'r') as f:
                                            ai_response = f.read().strip()
                                        response_found_at = matches[0]
                                        ctx.textual.dim_text(f"Found response at: {response_found_at}")
                                        break
                                    except Exception as e:
                                        ctx.textual.dim_text(f"Could not read from {matches[0]}: {e}")

                        if ai_response:
                            ctx.textual.success_text("✓ AI provided a response (will review all at the end)")
                            pending_responses[main_comment.id] = ai_response
                            processed_count += 1
                        else:
                            ctx.textual.warning_text("⚠ No AI response found - AI may have skipped this comment")
                            ctx.textual.dim_text(f"Searched for: {os.path.basename(response_file)}")
                            skipped_count += 1

                except Exception as e:
                    ctx.textual.error_text(f"AI review error: {e}")
                    import traceback
                    ctx.textual.dim_text(traceback.format_exc())
                    skipped_count += 1

            elif choice == "resolve":
                # Resolve the review thread using GraphQL node ID
                try:
                    thread_id = pr_thread.id
                    if not thread_id:
                        ctx.textual.error_text("Cannot resolve thread: missing thread ID")
                        skipped_count += 1
                    else:
                        with ctx.textual.loading("Resolving thread..."):
                            ctx.github.resolve_review_thread(thread_id)

                        ctx.textual.success_text("Thread resolved")
                        processed_count += 1
                except Exception as e:
                    ctx.textual.error_text(f"Failed to resolve thread: {e}")
                    skipped_count += 1

        # Review and send all pending AI responses
        if pending_responses:
            ctx.textual.text("")
            ctx.textual.text("")
            ctx.textual.bold_text(f"=== AI Responses Review ({len(pending_responses)} response(s)) ===")
            ctx.textual.text("")

            # Map comment IDs to thread info for display
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
                # "skip" - do nothing

            # Send all approved responses
            if responses_to_send:
                ctx.textual.text("")
                ctx.textual.primary_text(f"Sending {len(responses_to_send)} response(s)...")
                replied_count = 0

                for comment_id, response_text in responses_to_send.items():
                    try:
                        with ctx.textual.loading(f"Replying to comment {comment_id}..."):
                            ctx.github.reply_to_comment(pr_number, comment_id, response_text)
                        replied_count += 1
                    except Exception as e:
                        ctx.textual.error_text(f"Failed to reply to comment {comment_id}: {e}")

                ctx.textual.success_text(f"✓ Sent {replied_count} response(s)")
            else:
                ctx.textual.dim_text("No responses to send")

        # Send "Fixed in {hash}" replies for commits
        if comment_commits:
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
                replied_count = 0
                for comment_id, commit_hash in comment_commits.items():
                    try:
                        reply_text = f"Fixed in {commit_hash[:8]}"
                        with ctx.textual.loading(f"Replying to comment {comment_id}..."):
                            ctx.github.reply_to_comment(pr_number, comment_id, reply_text)
                        replied_count += 1
                        ctx.textual.dim_text(f"  ✓ Replied with: {reply_text}")
                    except Exception as e:
                        ctx.textual.warning_text(f"Failed to reply to comment {comment_id}: {e}")

                ctx.textual.success_text(f"✓ Sent {replied_count} auto-reply(s)")
            else:
                ctx.textual.dim_text("Skipped auto-replies")

        # All threads processed
        ctx.textual.text("")
        ctx.textual.success_text(f"Review complete! Processed {processed_count}, skipped {skipped_count} out of {len(review_threads)} thread(s)")
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
        if 'response_files' in locals():
            for response_file in response_files:
                try:
                    if os.path.exists(response_file):
                        os.remove(response_file)
                except Exception:
                    pass  # Silent cleanup

        # Cleanup worktree if it was created
        if worktree_created and worktree_path and ctx.git:
            try:
                with ctx.textual.loading("Cleaning up worktree..."):
                    ctx.git.remove_worktree(worktree_path, force=True)
                ctx.textual.dim_text("Worktree cleaned up")
            except Exception as e:
                ctx.textual.warning_text(f"Failed to cleanup worktree: {e}")


# Export for plugin registration
__all__ = [
    "select_pr_for_review_step",
    "fetch_pending_comments_step",
    "review_comments_step",
]
