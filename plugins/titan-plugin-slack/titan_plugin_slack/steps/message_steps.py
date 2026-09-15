"""Reusable Slack messaging steps for direct messages and later channels."""

import os

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Skip, Success, WorkflowContext, WorkflowResult
from ..formatting import SlackFormatter
from ..models import UISlackConversation


def prepare_message_destination_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Prepare a Slack message destination from the selected target(s).

    Requires:
        ctx.slack: An initialized SlackClient.

    Inputs (from ctx.data):
        slack_targets (list[UISlackTarget], optional): Selected Slack channel targets, when
            multiple channels were checked via a checklist (e.g.
            `select_default_or_search_channel_target`). Takes priority over `slack_target`.
        slack_target (UISlackTarget, optional): Selected Slack target. Must be a `user` or
            `channel` target. Used when `slack_targets` is not set.

    Outputs (saved to ctx.data):
        slack_conversation (UISlackConversation, optional): Resolved Slack destination
            conversation, when a single `slack_target` was used.
        slack_conversation_id (str, optional): Conversation or channel ID used for later message
            operations, when a single `slack_target` was used.
        slack_conversation_name (str, optional): User-facing name of the destination, set
            together with `slack_conversation_id`.
        slack_conversation_ids (list[str], optional): Conversation IDs for every channel in
            `slack_targets`, when multiple targets were used.
        slack_conversation_names (list[str], optional): User-facing names for every channel in
            `slack_conversation_ids`, set together with `slack_conversation_ids`.

    Returns:
        Success: If the Slack message destination(s) are ready.
        Error: If Slack is unavailable, no target is provided, or the Slack request fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Prepare Slack Message Destination")

    if not ctx.slack:
        ctx.textual.error_text("Slack client not available")
        ctx.textual.end_step("error")
        return Error("Slack client not available")

    targets = ctx.get("slack_targets")
    if targets:
        conversation_ids = [target.target_id for target in targets]
        conversation_names = [target.target_name for target in targets]
        ctx.textual.success_text(
            f"Slack channel destinations ready: {', '.join(conversation_names)}"
        )
        ctx.textual.end_step("success")
        return Success(
            "Slack channel destinations ready",
            metadata={
                "slack_conversation_ids": conversation_ids,
                "slack_conversation_names": conversation_names,
            },
        )

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
                        "slack_conversation_name": target.target_name,
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
                "slack_conversation_name": target.target_name,
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
    Post a plain-text Slack message to the prepared conversation(s).

    When `slack_conversation_ids` holds more than one conversation, the message is posted to
    each one independently: a conversation that fails is skipped with a warning while the rest
    still get the message, and the step only fails outright if every post fails.

    Requires:
        ctx.slack: An initialized SlackClient.

    Inputs (from ctx.data):
        slack_conversation_ids (list[str], optional): Slack conversation IDs to post into. Takes
            priority over `slack_conversation_id` when set.
        slack_conversation_id (str, optional): Single Slack conversation ID to post into. Used
            when `slack_conversation_ids` is not set.
        slack_message_text (str): Message body to post.
        slack_thread_ts (str, optional): Thread timestamp for replies. Only applied when posting
            to a single conversation.

    Outputs (saved to ctx.data):
        slack_message (UISlackPostedMessage, optional): Posted Slack message metadata, when a
            single conversation was used.
        slack_message_ts (str, optional): Timestamp of the posted message, when a single
            conversation was used.
        slack_message_channel (str, optional): Channel the message was posted to, when a single
            conversation was used.
        slack_messages (list[UISlackPostedMessage], optional): Posted message metadata for every
            conversation that succeeded, when multiple conversations were used.
        slack_message_channels (list[str], optional): Channels the message was successfully
            posted to, when multiple conversations were used.

    Returns:
        Success: If the Slack message is posted to at least one conversation.
        Error: If Slack is unavailable, required context is missing, or every post fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Post Slack Message")

    if not ctx.slack:
        ctx.textual.error_text("Slack client not available")
        ctx.textual.end_step("error")
        return Error("Slack client not available")

    message_text = ctx.get("slack_message_text")
    if not message_text:
        ctx.textual.error_text("Slack message text not found in context")
        ctx.textual.end_step("error")
        return Error("Slack message text not found in context")

    conversation_ids = ctx.get("slack_conversation_ids")
    if conversation_ids:
        conversation_names = ctx.get("slack_conversation_names") or []
        names_by_id = dict(zip(conversation_ids, conversation_names))

        posted_messages = []
        failed: list[tuple[str, str]] = []
        with ctx.textual.loading(f"Posting Slack message to {len(conversation_ids)} channel(s)..."):
            for conversation_id in conversation_ids:
                result = ctx.slack.post_message(conversation_id, message_text)
                match result:
                    case ClientSuccess(data=message):
                        posted_messages.append(message)
                    case ClientError(error_message=err):
                        failed.append((conversation_id, err))

        for message in posted_messages:
            display_name = names_by_id.get(message.channel, message.channel)
            ctx.textual.success_text(f"Slack message posted to {display_name}")
        for conversation_id, err in failed:
            display_name = names_by_id.get(conversation_id, conversation_id)
            ctx.textual.warning_text(f"Failed to post to {display_name}: {err}")

        if not posted_messages:
            ctx.textual.error_text("Failed to post Slack message to any selected channel")
            ctx.textual.end_step("error")
            return Error("Failed to post Slack message to any selected channel")

        ctx.textual.end_step("success")
        return Success(
            f"Slack message posted to {len(posted_messages)} channel(s)",
            metadata={
                "slack_messages": posted_messages,
                "slack_message_channels": [message.channel for message in posted_messages],
                "slack_failed_channels": [cid for cid, _ in failed],
                "slack_post_errors": failed,
            },
        )

    conversation_id = ctx.get("slack_conversation_id")
    if not conversation_id:
        ctx.textual.error_text("Slack conversation ID not found in context")
        ctx.textual.end_step("error")
        return Error("Slack conversation ID not found in context")

    conversation_name = ctx.get("slack_conversation_name")
    thread_ts = ctx.get("slack_thread_ts")

    with ctx.textual.loading("Posting Slack message..."):
        result = ctx.slack.post_message(
            conversation_id,
            message_text,
            thread_ts=thread_ts,
        )

    match result:
        case ClientSuccess(data=message):
            ctx.textual.success_text(f"Slack message posted to {conversation_name or message.channel}")
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


def upload_file_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Upload a local file to the prepared Slack conversation(s), with an optional message above it.

    When `slack_conversation_ids` holds more than one conversation, the file is uploaded to each
    one independently: a conversation that fails is skipped with a warning while the rest still
    get the file, and the step only fails outright if every upload fails.

    Requires:
        ctx.slack: An initialized SlackClient with the `files:write` scope.

    Inputs (from ctx.data):
        slack_file_path (str): Local path of the file to upload.
        slack_file_title (str, optional): Title shown on the Slack file. Defaults to the file name.
        slack_message_text (str, optional): Slack-ready text posted as the message above the file.
        slack_conversation_ids (list[str], optional): Conversation IDs to upload into; wins over `slack_conversation_id`.
        slack_conversation_id (str, optional): Single conversation ID, used when `slack_conversation_ids` is not set.
        slack_thread_ts (str, optional): Thread timestamp to share the file into; single conversation only.

    Outputs (saved to ctx.data):
        slack_uploaded_file (UISlackUploadedFile, optional): Uploaded file metadata, single conversation case.
        slack_uploaded_files (list[UISlackUploadedFile], optional): Uploaded file metadata per successful conversation.

    Returns:
        Success: If the file is uploaded to at least one conversation.
        Error: If Slack is unavailable, the file is missing, or every upload fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Upload File to Slack")

    if not ctx.slack:
        ctx.textual.error_text("Slack client not available")
        ctx.textual.end_step("error")
        return Error("Slack client not available")

    file_path = ctx.get("slack_file_path")
    if not file_path:
        ctx.textual.error_text("Slack file path not found in context")
        ctx.textual.end_step("error")
        return Error("Slack file path not found in context")
    if not os.path.isfile(file_path):
        ctx.textual.error_text(f"File does not exist: {file_path}")
        ctx.textual.end_step("error")
        return Error(f"File does not exist: {file_path}")

    title = ctx.get("slack_file_title") or os.path.basename(file_path)
    initial_comment = ctx.get("slack_message_text") or None

    conversation_ids = ctx.get("slack_conversation_ids")
    if conversation_ids:
        conversation_names = ctx.get("slack_conversation_names") or []
        names_by_id = dict(zip(conversation_ids, conversation_names))

        uploaded_files = []
        failed: list[tuple[str, str]] = []
        with ctx.textual.loading(f"Uploading file to {len(conversation_ids)} channel(s)..."):
            for conversation_id in conversation_ids:
                result = ctx.slack.upload_file(
                    conversation_id, file_path, title=title, initial_comment=initial_comment
                )
                match result:
                    case ClientSuccess(data=uploaded):
                        uploaded_files.append(uploaded)
                    case ClientError(error_message=err):
                        failed.append((conversation_id, err))

        for uploaded in uploaded_files:
            display_name = names_by_id.get(uploaded.channel, uploaded.channel)
            ctx.textual.success_text(f"File uploaded to {display_name}")
        for conversation_id, err in failed:
            display_name = names_by_id.get(conversation_id, conversation_id)
            ctx.textual.warning_text(f"Failed to upload to {display_name}: {err}")

        if not uploaded_files:
            ctx.textual.error_text("Failed to upload the file to any selected channel")
            ctx.textual.end_step("error")
            return Error("Failed to upload the file to any selected channel")

        ctx.textual.end_step("success")
        return Success(
            f"File uploaded to {len(uploaded_files)} channel(s)",
            metadata={
                "slack_uploaded_files": uploaded_files,
                "slack_failed_channels": [cid for cid, _ in failed],
                "slack_upload_errors": failed,
            },
        )

    conversation_id = ctx.get("slack_conversation_id")
    if not conversation_id:
        ctx.textual.error_text("Slack conversation ID not found in context")
        ctx.textual.end_step("error")
        return Error("Slack conversation ID not found in context")

    conversation_name = ctx.get("slack_conversation_name")
    thread_ts = ctx.get("slack_thread_ts")

    with ctx.textual.loading("Uploading file to Slack..."):
        result = ctx.slack.upload_file(
            conversation_id,
            file_path,
            title=title,
            initial_comment=initial_comment,
            thread_ts=thread_ts,
        )

    match result:
        case ClientSuccess(data=uploaded):
            ctx.textual.success_text(f"File uploaded to {conversation_name or uploaded.channel}")
            ctx.textual.end_step("success")
            return Success("Slack file uploaded", metadata={"slack_uploaded_file": uploaded})
        case ClientError(error_message=err):
            ctx.textual.error_text(err)
            ctx.textual.end_step("error")
            return Error(err)


__all__ = [
    "prepare_message_destination_step",
    "open_direct_message_step",
    "format_markdown_message_step",
    "prompt_message_body_step",
    "post_message_step",
    "upload_file_step",
]
