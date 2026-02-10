"""
Steps for reviewing and addressing PR comments.
"""
import re
import threading
from typing import List, Optional
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip, Exit
from titan_cli.ui.tui.widgets import ChoiceOption, OptionItem, CommentThread
from ..models import PRComment


def _format_diff_hunk(diff_hunk: str, comment_line: Optional[int]) -> str:
    """
    Format a diff hunk to show code context with the commented line highlighted.

    Args:
        diff_hunk: The diff hunk from GitHub (includes @@ header and context)
        comment_line: The line number where the comment was made (None for non-review comments)

    Returns:
        Formatted markdown with highlighted line
    """
    if not diff_hunk:
        return ""

    lines = diff_hunk.split('\n')
    if not lines:
        return ""

    # Parse the @@ header to get starting line number
    # Format: @@ -old_start,old_lines +new_start,new_lines @@
    header_match = re.match(r'@@ -\d+,?\d* \+(\d+),?\d* @@', lines[0])
    if not header_match:
        # If we can't parse, just return the diff as-is
        return f"```diff\n{diff_hunk}\n```"

    start_line = int(header_match.group(1))
    current_line = start_line

    # Build formatted output with line numbers
    formatted_lines = []

    for line in lines[1:]:  # Skip @@ header
        # Handle diff markers
        if line.startswith('+'):
            # Added line - this is in the new file
            line_num = current_line
            line_content = line[1:]  # Remove + prefix

            # Highlight if this is the commented line
            if comment_line and current_line == comment_line:
                formatted_lines.append(f"**→ {line_num:4d} | {line_content}**  ⬅ 💬")
            else:
                formatted_lines.append(f"+ {line_num:4d} | {line_content}")

            current_line += 1
        elif line.startswith('-'):
            # Removed line - don't increment line counter
            line_content = line[1:]  # Remove - prefix
            formatted_lines.append(f"- {'':4s} | ~~{line_content}~~")
        elif line.startswith(' '):
            # Context line (unchanged)
            line_num = current_line
            line_content = line[1:]  # Remove space prefix

            # Highlight if this is the commented line (can happen in context lines too)
            if comment_line and current_line == comment_line:
                formatted_lines.append(f"**→ {line_num:4d} | {line_content}**  ⬅ 💬")
            else:
                formatted_lines.append(f"  {line_num:4d} | {line_content}")

            current_line += 1
        else:
            # Other lines (shouldn't happen normally)
            formatted_lines.append(f"  {'':4s} | {line}")

    # Limit context to ~5 lines around the commented line (like GitHub)
    if comment_line and len(formatted_lines) > 11:  # More than 5 before + comment + 5 after
        # Find the index of the commented line
        comment_idx = None
        for idx, line in enumerate(formatted_lines):
            if "💬" in line:
                comment_idx = idx
                break

        if comment_idx is not None:
            # Show 3 lines before and 3 lines after (like GitHub UI)
            start = max(0, comment_idx - 3)
            end = min(len(formatted_lines), comment_idx + 4)
            formatted_lines = formatted_lines[start:end]

            if start > 0:
                formatted_lines.insert(0, "  ... (lines above hidden)")
            if end < len(formatted_lines):
                formatted_lines.append("  ... (lines below hidden)")

    return "```\n" + "\n".join(formatted_lines) + "\n```"


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
    Fetch unresolved review comments for the selected PR.

    Only fetches threads that are NOT marked as resolved in GitHub.
    Does NOT filter by author responses - all unresolved threads are shown.

    Requires (from ctx.data):
        selected_pr_number (int): The PR number

    Outputs (saved to ctx.data):
        all_comments (List[PRComment]): ALL unresolved comments (needed for threading)
        pending_comment_ids (Set[int]): IDs of top-level comments (threads to review)

    Returns:
        Success: Comments fetched
        Skip: No unresolved comments
        Error: Failed to fetch comments
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
        # Fetch ALL comments (exclude resolved threads)
        with ctx.textual.loading(f"Fetching comments for PR #{pr_number}..."):
            all_comments = ctx.github.get_pr_comments(pr_number, include_resolved=False)

        if not all_comments:
            ctx.textual.dim_text(f"No unresolved comments found for PR #{pr_number}")
            ctx.textual.end_step("skip")
            return Exit("No unresolved comments")

        # Get top-level comments (threads to review)
        top_level_comments = [c for c in all_comments if not c.in_reply_to_id]
        pending_ids = {c.id for c in top_level_comments}

        # Show summary
        ctx.textual.success_text(f"Found {len(top_level_comments)} unresolved thread(s)")
        ctx.textual.text("")

        # Save to context
        metadata = {
            "all_comments": all_comments,  # All comments for threading
            "pending_comment_ids": pending_ids,  # Top-level comment IDs to review
            "total_pending": len(top_level_comments),
        }

        ctx.textual.end_step("success")

        return Success(
            f"Found {len(top_level_comments)} unresolved threads",
            metadata=metadata
        )

    except Exception as e:
        ctx.textual.error_text(f"Failed to fetch comments: {e}")
        ctx.textual.end_step("error")
        return Error(str(e))


def _group_comment_threads(comments: List[PRComment]) -> List[List[PRComment]]:
    """
    Group comments into conversation threads, handling nested replies.

    Args:
        comments: List of all comments

    Returns:
        List of threads, where each thread is a list of related comments in order
    """
    if not comments:
        return []

    # Find all replies for each comment (recursively)
    def get_all_replies(comment_id: int) -> List[PRComment]:
        """Recursively get all replies to a comment"""
        replies = []
        for comment in comments:
            if comment.in_reply_to_id == comment_id:
                replies.append(comment)
                # Recursively add replies to this reply
                replies.extend(get_all_replies(comment.id))
        return replies

    # Build threads starting from top-level comments (those without in_reply_to_id)
    threads = []
    processed_ids = set()

    for comment in comments:
        # Skip if already processed
        if comment.id in processed_ids:
            continue

        # Skip if it's a reply (will be included with its parent thread)
        if comment.in_reply_to_id:
            continue

        # This is a top-level comment - start a new thread
        thread = [comment]
        processed_ids.add(comment.id)

        # Get all replies (recursively)
        replies = get_all_replies(comment.id)
        for reply in replies:
            thread.append(reply)
            processed_ids.add(reply.id)

        threads.append(thread)

    # Sort threads by creation time of the first comment (chronological order)
    threads.sort(key=lambda thread: thread[0].created_at if thread else "")

    return threads


def review_comments_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Review all unresolved comment threads one by one and take action.

    Shows all threads that are NOT marked as resolved, regardless of who commented.

    Requires (from ctx.data):
        selected_pr_number (int): The PR number
        all_comments (List[PRComment]): ALL unresolved comments
        pending_comment_ids (Set[int]): IDs of top-level comments (threads)

    Returns:
        Success: All comments processed
        Skip: User cancelled review
        Error: Failed to process comments
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Review Comments")

    # Get data from context
    pr_number = ctx.get("selected_pr_number")
    all_comments: List[PRComment] = ctx.get("all_comments", [])
    pending_ids: set = ctx.get("pending_comment_ids", set())

    if not pr_number or not all_comments or not pending_ids:
        ctx.textual.end_step("error")
        return Error("Missing required data")

    # Group ALL comments into threads
    all_threads = _group_comment_threads(all_comments)

    # Filter to only threads where the main comment is pending
    pending_threads = [
        thread for thread in all_threads
        if thread[0].id in pending_ids
    ]

    if not pending_threads:
        ctx.textual.dim_text("No pending comment threads")
        ctx.textual.end_step("skip")
        return Skip("No pending threads")

    comment_threads = pending_threads

    # Loop through all comment threads
    processed_count = 0
    skipped_count = 0

    for thread_idx, thread in enumerate(comment_threads):
        # thread[0] is the main comment
        comment = thread[0]

        # Prepare comment body with file/line info if it's a review comment
        comment_body_parts = []

        if comment.is_review_comment and comment.path:
            line_info = f"Line {comment.line}" if comment.line else "General file comment"
            comment_body_parts.append(f"**File:** `{comment.path}` • {line_info}\n")

            # Show diff context if available
            if comment.diff_hunk:
                comment_body_parts.append("**Code Context:**")
                # Parse and format diff hunk to show context with highlighted line
                formatted_code = _format_diff_hunk(comment.diff_hunk, comment.line)
                comment_body_parts.append(formatted_code)
                comment_body_parts.append("")
            elif comment.line:
                # No diff hunk but we have a line number
                comment_body_parts.append(f"_(Comment on line {comment.line}, no code context available)_\n")

        # Add comment body
        if comment.body and comment.body.strip():
            comment_body_parts.append(comment.body)

        # Add replies if any
        if len(thread) > 1:
            comment_body_parts.append(f"\n💬 **{len(thread) - 1} repl{'y' if len(thread) == 2 else 'ies'}:**\n")
            for reply in thread[1:]:
                reply_body = reply.body.strip() if reply.body else "_(empty comment)_"
                comment_body_parts.append(f"└─ **{reply.user.login}** • {reply.created_at}")
                comment_body_parts.append(f"   {reply_body}\n")

        full_body = "\n".join(comment_body_parts) if comment_body_parts else None

        # Prepare action options
        options = [
            ChoiceOption(value="reply", label="Reply manually", variant="primary"),
            ChoiceOption(value="ai_suggest", label="Get AI suggestion", variant="default"),
            ChoiceOption(value="skip", label="Skip for now", variant="default"),
            ChoiceOption(value="resolve", label="Resolve thread", variant="success"),
        ]

        # Add "Exit" option if not the last comment
        if thread_idx < len(comment_threads) - 1:
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
            author=comment.user.login,
            date=str(comment.created_at),
            body=full_body,
            thread_number=f"Thread {thread_idx + 1} of {len(comment_threads)}",
            is_outdated=False,  # Could check comment.original_position vs position
            options=options,
            on_select=on_choice_selected
        )

        ctx.textual.text("")
        ctx.textual.mount(thread_widget)
        # No manual scroll - PromptChoice inside CommentThread will auto-scroll when mounted

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
                    "reply": "Replying manually",
                    "ai_suggest": "Getting AI suggestion",
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
                    "total_threads": len(comment_threads),
                    "total_pending": len(pending_ids),
                }
            )

        if choice == "skip":
            skipped_count += 1
            continue

        elif choice == "reply":
            # Manual reply
            ctx.textual.text("")
            reply_text = ctx.textual.ask_multiline(
                "Enter your reply:",
                default=""
            )

            if reply_text and reply_text.strip():
                try:
                    with ctx.textual.loading("Posting reply..."):
                        ctx.github.reply_to_comment(pr_number, comment.id, reply_text)

                    ctx.textual.success_text("Reply posted successfully")
                    processed_count += 1
                except Exception as e:
                    ctx.textual.error_text(f"Failed to post reply: {e}")
                    skipped_count += 1
            else:
                ctx.textual.warning_text("Empty reply, skipping")
                skipped_count += 1

        elif choice == "ai_suggest":
            # AI suggestion
            if not ctx.ai or not ctx.ai.is_available():
                ctx.textual.warning_text("AI not configured")
                skipped_count += 1
                continue

            try:
                # Build context for AI
                from titan_cli.ai.models import AIMessage

                pr_title = ctx.get("selected_pr_title", "")

                context_parts = [
                    f"You are helping address a code review comment on PR: {pr_title}",
                    f"\nReviewer: {comment.user.login}",
                ]

                if comment.is_review_comment and comment.path:
                    context_parts.append(f"File: {comment.path}")
                    if comment.diff_hunk:
                        context_parts.append(f"\nCode context:\n```diff\n{comment.diff_hunk}\n```")

                context_parts.append(f"\nComment:\n{comment.body}")
                context_parts.append("\nProvide a helpful, professional reply addressing this comment. Be concise and constructive.")

                prompt = "\n".join(context_parts)

                # Get AI suggestion (generic for any model)
                messages = [AIMessage(role="user", content=prompt)]
                with ctx.textual.loading("Generating AI suggestion..."):
                    response = ctx.ai.generate(messages)
                    ai_response = response.content.strip()

                if not ai_response or not ai_response.strip():
                    ctx.textual.warning_text("AI returned empty response")
                    skipped_count += 1
                    continue

                # Show AI suggestion
                ctx.textual.text("")
                ctx.textual.bold_text("AI Suggestion:")
                ctx.textual.markdown(ai_response)
                ctx.textual.text("")

                # No manual scroll - PromptChoice will auto-scroll when mounted

                # Ask what to do with suggestion
                ai_options = [
                    ChoiceOption(value="use", label="Use as-is", variant="primary"),
                    ChoiceOption(value="edit", label="Edit", variant="default"),
                    ChoiceOption(value="reject", label="Reject", variant="error"),
                ]

                ai_choice = ctx.textual.ask_choice(
                    "What would you like to do with this suggestion?",
                    ai_options
                )

                if ai_choice == "reject":
                    ctx.textual.warning_text("AI suggestion rejected")
                    skipped_count += 1
                    continue

                reply_text = ai_response

                if ai_choice == "edit":
                    ctx.textual.text("")
                    edited_reply = ctx.textual.ask_multiline(
                        "Edit the reply:",
                        default=ai_response
                    )

                    if edited_reply and edited_reply.strip():
                        reply_text = edited_reply
                    else:
                        ctx.textual.warning_text("Empty reply, skipping")
                        skipped_count += 1
                        continue

                # Post the reply
                try:
                    with ctx.textual.loading("Posting reply..."):
                        ctx.github.reply_to_comment(pr_number, comment.id, reply_text)

                    ctx.textual.success_text("Reply posted successfully")
                    processed_count += 1
                except Exception as e:
                    ctx.textual.error_text(f"Failed to post reply: {e}")
                    skipped_count += 1

            except Exception as e:
                ctx.textual.error_text(f"AI error: {e}")
                skipped_count += 1

        elif choice == "resolve":
            # Resolve the review thread
            try:
                # Get the node_id from the first comment in the thread (the root comment)
                root_comment = thread[0]
                if not root_comment.node_id:
                    ctx.textual.error_text("Cannot resolve thread: missing node_id")
                    skipped_count += 1
                else:
                    with ctx.textual.loading("Resolving thread..."):
                        ctx.github.resolve_review_thread(root_comment.node_id)

                    ctx.textual.success_text("Thread resolved")
                    processed_count += 1
            except Exception as e:
                ctx.textual.error_text(f"Failed to resolve thread: {e}")
                skipped_count += 1

    # All comments processed
    ctx.textual.text("")
    ctx.textual.success_text(f"Review complete! Processed {processed_count}, skipped {skipped_count} out of {len(comment_threads)} thread(s)")
    ctx.textual.end_step("success")

    return Success(
        f"Reviewed {len(comment_threads)} comment thread(s)",
        metadata={
            "processed_count": processed_count,
            "skipped_count": skipped_count,
            "total_threads": len(comment_threads),
            "total_comments": len(pending_ids),
        }
    )


# Export for plugin registration
__all__ = [
    "select_pr_for_review_step",
    "fetch_pending_comments_step",
    "review_comments_step",
]
