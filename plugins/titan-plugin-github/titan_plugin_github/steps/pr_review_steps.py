"""
Steps for reviewing and addressing PR comments.
"""
import re
from typing import List, Optional
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_cli.ui.tui.widgets import ChoiceOption, OptionItem
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
            ctx.textual.end_step("skip")
            return Skip("No open PRs found")

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
            return Skip("User cancelled PR selection")

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
    Fetch pending review comments for the selected PR.

    Requires (from ctx.data):
        selected_pr_number (int): The PR number

    Outputs (saved to ctx.data):
        all_comments (List[PRComment]): ALL comments (needed for threading)
        pending_comment_ids (Set[int]): IDs of pending comments (main threads to review)

    Returns:
        Success: Comments fetched
        Skip: No pending comments
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
        # Fetch ALL comments (needed to build threads)
        with ctx.textual.loading(f"Fetching comments for PR #{pr_number}..."):
            all_comments = ctx.github.get_pr_comments(pr_number)
            # Also get which ones are pending (no response from author)
            pending_comments = ctx.github.get_pending_comments(pr_number)

        if not pending_comments:
            ctx.textual.dim_text(f"No pending comments found for PR #{pr_number}")
            ctx.textual.end_step("skip")
            return Skip("No pending comments")

        # Create set of pending comment IDs for quick lookup
        pending_ids = {c.id for c in pending_comments}

        # Show summary
        ctx.textual.success_text(f"Found {len(pending_comments)} pending comment(s)")
        ctx.textual.text("")

        # Save to context
        metadata = {
            "all_comments": all_comments,  # All comments for threading
            "pending_comment_ids": pending_ids,  # Which ones to review
            "total_pending": len(pending_comments),
        }

        ctx.textual.end_step("success")

        return Success(
            f"Found {len(pending_comments)} pending comments",
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

    return threads


def review_comments_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Review all pending comments one by one and take action.

    Requires (from ctx.data):
        selected_pr_number (int): The PR number
        all_comments (List[PRComment]): ALL comments
        pending_comment_ids (Set[int]): IDs of pending main comments

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
        # Display comment info
        ctx.textual.text("")
        ctx.textual.bold_text(f"Thread {thread_idx + 1} of {len(comment_threads)}")
        ctx.textual.text("")

        # Show comment author and date
        ctx.textual.dim_text(f"From: {comment.user.login} • {comment.created_at}")

        # Show file and line if it's a review comment
        if comment.is_review_comment and comment.path:
            line_info = f"Line {comment.line}" if comment.line else "General file comment"
            ctx.textual.dim_text(f"File: {comment.path} • {line_info}")
            ctx.textual.text("")

            # Show diff context if available
            if comment.diff_hunk:
                ctx.textual.bold_text("Code Context:")
                # Parse and format diff hunk to show context with highlighted line
                formatted_code = _format_diff_hunk(comment.diff_hunk, comment.line)
                ctx.textual.markdown(formatted_code)
                ctx.textual.text("")
            elif comment.line:
                # No diff hunk but we have a line number
                ctx.textual.dim_text(f"(Comment on line {comment.line}, no code context available)")
                ctx.textual.text("")

        # Show comment body
        ctx.textual.bold_text("Comment:")
        if comment.body and comment.body.strip():
            ctx.textual.markdown(comment.body)
        else:
            ctx.textual.dim_text("(empty comment)")
        ctx.textual.text("")

        # Show replies in the thread if any
        if len(thread) > 1:
            ctx.textual.dim_text(f"💬 {len(thread) - 1} repl{'y' if len(thread) == 2 else 'ies'}:")
            ctx.textual.text("")
            for reply in thread[1:]:
                ctx.textual.dim_text(f"  └─ {reply.user.login} • {reply.created_at}")
                # Handle empty bodies (common with some bots)
                reply_body = reply.body.strip() if reply.body else ""
                if reply_body:
                    ctx.textual.text(f"     {reply_body}")
                else:
                    ctx.textual.dim_text("     (empty comment)")
                ctx.textual.text("")

        # Scroll to show options below
        ctx.textual.scroll_to_end()

        # Ask user what to do
        options = [
            ChoiceOption(value="reply", label="Reply manually", variant="primary"),
            ChoiceOption(value="ai_suggest", label="Get AI suggestion", variant="default"),
            ChoiceOption(value="skip", label="Skip for now", variant="default"),
            ChoiceOption(value="resolve", label="Mark as addressed", variant="success"),
        ]

        # Add "Exit" option if not the last comment
        if thread_idx < len(comment_threads) - 1:
            options.append(
                ChoiceOption(value="exit", label="Exit review", variant="error")
            )

        choice = ctx.textual.ask_choice(
            "What would you like to do?",
            options
        )

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
            ctx.textual.dim_text("Skipped comment")
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

                # Scroll to show buttons
                ctx.textual.scroll_to_end()

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
            # Mark as addressed (just add a simple comment)
            try:
                with ctx.textual.loading("Marking as addressed..."):
                    ctx.github.reply_to_comment(
                        pr_number,
                        comment.id,
                        "✓ Addressed"
                    )

                ctx.textual.success_text("Marked as addressed")
                processed_count += 1
            except Exception as e:
                ctx.textual.error_text(f"Failed to mark as addressed: {e}")
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
