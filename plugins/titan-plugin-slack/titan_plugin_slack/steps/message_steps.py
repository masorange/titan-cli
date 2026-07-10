"""Reusable Slack messaging steps for direct messages and later channels."""

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Skip, Success, WorkflowContext, WorkflowResult
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


def prompt_message_body_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Capture a multiline Slack message body for later posting.

    Inputs (from ctx.data):
        slack_message_text (str, optional): Pre-filled message text. If already present, the prompt is skipped.

    Outputs (saved to ctx.data):
        slack_message_text (str): Message text to post later.

    Returns:
        Success: If the message body is captured successfully.
        Skip: If the message body already exists in context.
        Error: If the user cancels or the message body is empty.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Compose Slack Message")

    existing = ctx.get("slack_message_text")
    existing_stripped = str(existing).strip() if existing else ""
    if existing_stripped:
        ctx.textual.dim_text("Slack message text already provided, skipping prompt.")
        ctx.textual.end_step("skip")
        return Skip(
            "Slack message text already provided",
            metadata={"slack_message_text": existing_stripped},
        )

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
        metadata={"slack_message_text": body.strip()},
    )


def post_message_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Post a plain-text Slack message to the prepared conversation.

    Requires:
        ctx.slack: An initialized SlackClient.

    Inputs (from ctx.data):
        slack_conversation_id (str): Slack conversation ID to post into.
        slack_message_text (str): Message body to post.
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

    with ctx.textual.loading("Posting Slack message..."):
        result = ctx.slack.post_message(
            conversation_id,
            message_text,
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
    "prompt_message_body_step",
    "post_message_step",
]
