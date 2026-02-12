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

    try:
        # Get data from context
        pr_number = ctx.get("selected_pr_number")
        review_threads: List[PRReviewThread] = ctx.get("review_threads", [])

        if not pr_number or not review_threads:
            ctx.textual.end_step("error")
            return Error("Missing required data")

        if not review_threads:
            ctx.textual.dim_text("No pending comment threads")
            ctx.textual.end_step("skip")
            return Skip("No pending threads")

        # Loop through all review threads
        processed_count = 0
        skipped_count = 0

        for thread_idx, pr_thread in enumerate(review_threads):
            # Convert PRReviewThread to UICommentThread
            ui_thread = UICommentThread.from_review_thread(pr_thread)

            # Prepare action options
            options = [
                ChoiceOption(value="reply", label="Reply manually", variant="primary"),
                ChoiceOption(value="ai_suggest", label="Get AI suggestion", variant="default"),
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
                        "total_threads": len(review_threads),
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
                        # Get main comment ID from the network model
                        main_comment_id = pr_thread.main_comment.id
                        with ctx.textual.loading("Posting reply..."):
                            ctx.github.reply_to_comment(pr_number, main_comment_id, reply_text)

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
                    main_comment = pr_thread.main_comment

                    context_parts = [
                        f"You are helping address a code review comment on PR: {pr_title}",
                        f"\nReviewer: {main_comment.author.login}",
                    ]

                    if main_comment.path:
                        context_parts.append(f"File: {main_comment.path}")
                        if main_comment.diff_hunk:
                            context_parts.append(f"\nCode context:\n```diff\n{main_comment.diff_hunk}\n```")

                    context_parts.append(f"\nComment:\n{main_comment.body}")
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
                        ChoiceOption(value="use", label="Use", variant="primary"),
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
                        main_comment_id = pr_thread.main_comment.id
                        with ctx.textual.loading("Posting reply..."):
                            ctx.github.reply_to_comment(pr_number, main_comment_id, reply_text)

                        ctx.textual.success_text("Reply posted successfully")
                        processed_count += 1
                    except Exception as e:
                        ctx.textual.error_text(f"Failed to post reply: {e}")
                        skipped_count += 1

                except Exception as e:
                    ctx.textual.error_text(f"AI error: {e}")
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

        # All threads processed
        ctx.textual.text("")
        ctx.textual.success_text(f"Review complete! Processed {processed_count}, skipped {skipped_count} out of {len(review_threads)} thread(s)")
        ctx.textual.end_step("success")

        return Success(
            f"Reviewed {len(review_threads)} comment thread(s)",
            metadata={
                "processed_count": processed_count,
                "skipped_count": skipped_count,
                "total_threads": len(review_threads),
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


# Export for plugin registration
__all__ = [
    "select_pr_for_review_step",
    "fetch_pending_comments_step",
    "review_comments_step",
]
