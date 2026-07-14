"""Reusable Slack messaging steps for direct messages and later channels."""

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Skip, Success, WorkflowContext, WorkflowResult
from ..block_formatting import SlackBlockFormatter
from ..formatting import SlackFormatter
from ..models import UISlackConversation


def prepare_message_destination_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Prepare a Slack message destination from the selected target.

    Requires:
        ctx.slack: An initialized SlackClient.

    Inputs (from ctx.data):
        slack_target (UISlackTarget): Selected Slack target. Must be a `user` or `channel` target.

    Outputs (saved to ctx.data):
        slack_conversation (UISlackConversation): Resolved Slack destination conversation.
        slack_conversation_id (str): Conversation or channel ID used for later message operations.

    Returns:
        Success: If the Slack message destination is ready.
        Error: If Slack is unavailable, the target is missing or invalid, or the Slack request fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Prepare Slack Message Destination")

    if not ctx.slack:
        ctx.textual.error_text("Slack client not available")
        ctx.textual.end_step("error")
        return Error("Slack client not available")

    target = ctx.get("slack_target")
    if not target:
        ctx.textual.error_text("Slack target not found in context")
        ctx.textual.end_step("error")
        return Error("Slack target not found in context")

    if target.target_type == "user":
        with ctx.textual.loading("Opening Slack direct message..."):
            result = ctx.slack.open_direct_message(target.target_id)

        match result:
            case ClientSuccess(data=conversation):
                ctx.textual.success_text(
                    f"Slack direct message ready: {conversation.id} for {target.target_name}"
                )
                ctx.textual.end_step("success")
                return Success(
                    "Slack direct message ready",
                    metadata={
                        "slack_conversation": conversation,
                        "slack_conversation_id": conversation.id,
                    },
                )
            case ClientError(error_message=err):
                ctx.textual.error_text(err)
                ctx.textual.end_step("error")
                return Error(err)

    if target.target_type == "channel":
        conversation = UISlackConversation(
            id=target.target_id,
            is_im=False,
            team_id=target.team_id,
        )
        ctx.textual.success_text(
            f"Slack channel destination ready: {target.target_name} ({conversation.id})"
        )
        ctx.textual.end_step("success")
        return Success(
            "Slack channel destination ready",
            metadata={
                "slack_conversation": conversation,
                "slack_conversation_id": conversation.id,
            },
        )

    ctx.textual.error_text("Slack message destinations require a user or channel target")
    ctx.textual.end_step("error")
    return Error("Slack message destinations require a user or channel target")


def open_direct_message_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Open or reuse a direct message conversation for the selected Slack user target.

    Requires:
        ctx.slack: An initialized SlackClient.

    Inputs (from ctx.data):
        slack_target (UISlackTarget): Selected Slack target. Must be a `user` target.

    Outputs (saved to ctx.data):
        slack_conversation (UISlackConversation): Opened or reused Slack conversation.
        slack_conversation_id (str): Conversation ID used for later message operations.

    Returns:
        Success: If the direct message conversation is ready.
        Error: If Slack is unavailable, the target is missing or invalid, or the Slack request fails.
    """
    target = ctx.get("slack_target")
    if target and target.target_type != "user":
        if ctx.textual:
            ctx.textual.begin_step("Open Slack Direct Message")
            ctx.textual.error_text("Direct messages require a Slack user target")
            ctx.textual.end_step("error")
        return Error("Direct messages require a Slack user target")

    return prepare_message_destination_step(ctx)


def format_markdown_message_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Convert a standard Markdown message into Slack mrkdwn, if provided.

    Leaves an already Slack-ready message untouched, so a caller that already
    built Slack-specific content (e.g. a prebuilt table) is never
    double-converted.

    Inputs (from ctx.data):
        slack_message_text (str, optional): Already Slack-ready text. If present, this step does
            nothing and leaves it untouched.
        slack_message_markdown (str, optional): Standard Markdown text to convert to Slack mrkdwn.
            Ignored when `slack_message_text` is already present.

    Outputs (saved to ctx.data):
        slack_message_text (str): Slack mrkdwn-ready message text, when `slack_message_markdown` was converted.

    Returns:
        Skip: If `slack_message_text` is already set, or neither input is provided (a later step
            can still prompt the user to compose one interactively).
        Success: If `slack_message_markdown` was converted successfully.
        Error: If the Textual UI context is not available.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Format Slack Message")

    if ctx.get("slack_message_text"):
        ctx.textual.dim_text("Slack message text already provided - using as-is.")
        ctx.textual.end_step("skip")
        return Skip("Slack message text already provided")

    markdown = ctx.get("slack_message_markdown")
    if not markdown:
        ctx.textual.dim_text("No message provided - you will be asked to compose one.")
        ctx.textual.end_step("skip")
        return Skip("No message provided")

    formatted = SlackFormatter.to_mrkdwn(markdown)
    ctx.textual.success_text("Converted Markdown message to Slack mrkdwn")
    ctx.textual.end_step("success")
    return Success(
        "Converted Markdown message to Slack mrkdwn",
        metadata={"slack_message_text": formatted},
    )


def format_blockkit_message_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Convert a standard Markdown message into Slack Block Kit blocks, if provided.

    Leaves already Slack-ready blocks untouched, so a caller that already
    built its own blocks (e.g. buttons via `SlackBlockFormatter.section`
    and friends) is never double-converted. Also fills in `slack_message_text`
    from the same Markdown when missing, since Slack uses it as the
    notification/accessibility fallback for messages posted with `blocks`.

    Inputs (from ctx.data):
        slack_message_blocks (list[dict], optional): Already Slack-ready blocks. If present,
            this step does nothing and leaves them untouched.
        slack_message_markdown (str, optional): Standard Markdown text to convert to Block Kit
            blocks. Ignored when `slack_message_blocks` is already present.
        slack_message_text (str, optional): Slack-ready fallback text. Left untouched if already
            present; otherwise derived from `slack_message_markdown`.

    Outputs (saved to ctx.data):
        slack_message_blocks (list[dict]): Block Kit blocks, when `slack_message_markdown` was converted.
        slack_message_text (str): Slack mrkdwn fallback text, when not already present.

    Returns:
        Skip: If `slack_message_blocks` is already set, or neither input is provided (a later step
            can still prompt the user to compose one interactively).
        Success: If `slack_message_markdown` was converted successfully.
        Error: If the Textual UI context is not available.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Format Slack Message (Block Kit)")

    if ctx.get("slack_message_blocks"):
        ctx.textual.dim_text("Slack message blocks already provided - using as-is.")
        ctx.textual.end_step("skip")
        return Skip("Slack message blocks already provided")

    markdown = ctx.get("slack_message_markdown")
    if not markdown:
        ctx.textual.dim_text("No message provided - you will be asked to compose one.")
        ctx.textual.end_step("skip")
        return Skip("No message provided")

    blocks = SlackBlockFormatter.to_blocks(markdown)
    metadata = {"slack_message_blocks": blocks}
    if not ctx.get("slack_message_text"):
        metadata["slack_message_text"] = SlackFormatter.to_mrkdwn(markdown)

    ctx.textual.success_text("Converted Markdown message to Slack Block Kit blocks")
    ctx.textual.end_step("success")
    return Success(
        "Converted Markdown message to Slack Block Kit blocks",
        metadata=metadata,
    )


def prompt_message_body_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Capture a multiline Slack message for later formatting and posting.

    Captured text is saved as `slack_message_markdown` (not `slack_message_text`)
    so a later step (e.g. `format_markdown_message`) converts it to Slack
    mrkdwn just like a caller-provided Markdown message would be - typed input
    shouldn't be posted as raw, unconverted Markdown.

    Inputs (from ctx.data):
        slack_message_text (str, optional): Already Slack-ready message text. If present, the prompt is skipped.
        slack_message_markdown (str, optional): Standard Markdown message already provided by a caller. If
            present (and slack_message_text isn't), the prompt is skipped.

    Outputs (saved to ctx.data):
        slack_message_markdown (str): Captured message text, to be converted to Slack mrkdwn by a later step.

    Returns:
        Success: If the message body is captured successfully.
        Skip: If a message was already provided by the caller.
        Error: If the user cancels or the message body is empty.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Compose Slack Message")

    existing_text = str(ctx.get("slack_message_text") or "").strip()
    existing_markdown = str(ctx.get("slack_message_markdown") or "").strip()
    if existing_text or existing_markdown:
        ctx.textual.dim_text("Slack message already provided, skipping prompt.")
        ctx.textual.end_step("skip")
        return Skip("Slack message already provided")

    try:
        body = ctx.textual.ask_multiline("Enter the Slack message:", default="")
    except (KeyboardInterrupt, EOFError):
        ctx.textual.end_step("error")
        return Error("User cancelled Slack message composition")
    except Exception as exc:
        ctx.textual.end_step("error")
        return Error(f"Failed to prompt for Slack message: {exc}", exception=exc)

    if not body or not body.strip():
        ctx.textual.error_text("Slack message text cannot be empty")
        ctx.textual.end_step("error")
        return Error("Slack message text cannot be empty")

    ctx.textual.success_text("Slack message composed")
    ctx.textual.end_step("success")
    return Success(
        "Slack message text captured",
        metadata={"slack_message_markdown": body.strip()},
    )


def post_message_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Post a Slack message to the prepared conversation.

    Posts Block Kit blocks when `slack_message_blocks` is present in context
    (e.g. produced by `format_blockkit_message`), falling back to a plain
    mrkdwn message otherwise. `slack_message_text` is always sent alongside
    blocks, since Slack uses it as the notification/accessibility fallback.

    Requires:
        ctx.slack: An initialized SlackClient.

    Inputs (from ctx.data):
        slack_conversation_id (str): Slack conversation ID to post into.
        slack_message_text (str): Message body to post.
        slack_message_blocks (list[dict], optional): Block Kit blocks to post alongside the text.
        slack_thread_ts (str, optional): Thread timestamp for replies.

    Outputs (saved to ctx.data):
        slack_message (UISlackPostedMessage): Posted Slack message metadata.
        slack_message_ts (str): Timestamp of the posted message.
        slack_message_channel (str): Channel or conversation ID where the message was posted.

    Returns:
        Success: If the Slack message is posted successfully.
        Error: If Slack is unavailable, required context is missing, or the Slack request fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Post Slack Message")

    if not ctx.slack:
        ctx.textual.error_text("Slack client not available")
        ctx.textual.end_step("error")
        return Error("Slack client not available")

    conversation_id = ctx.get("slack_conversation_id")
    if not conversation_id:
        ctx.textual.error_text("Slack conversation ID not found in context")
        ctx.textual.end_step("error")
        return Error("Slack conversation ID not found in context")

    message_text = ctx.get("slack_message_text")
    if not message_text:
        ctx.textual.error_text("Slack message text not found in context")
        ctx.textual.end_step("error")
        return Error("Slack message text not found in context")

    thread_ts = ctx.get("slack_thread_ts")
    blocks = ctx.get("slack_message_blocks")

    with ctx.textual.loading("Posting Slack message..."):
        result = ctx.slack.post_message(
            conversation_id,
            message_text,
            blocks=blocks,
            thread_ts=thread_ts,
        )

    match result:
        case ClientSuccess(data=message):
            ctx.textual.success_text(f"Slack message posted to {message.channel}")
            ctx.textual.end_step("success")
            return Success(
                "Slack message posted",
                metadata={
                    "slack_message": message,
                    "slack_message_ts": message.ts,
                    "slack_message_channel": message.channel,
                },
            )
        case ClientError(error_message=err):
            ctx.textual.error_text(err)
            ctx.textual.end_step("error")
            return Error(err)


__all__ = [
    "prepare_message_destination_step",
    "open_direct_message_step",
    "format_markdown_message_step",
    "format_blockkit_message_step",
    "prompt_message_body_step",
    "post_message_step",
]
