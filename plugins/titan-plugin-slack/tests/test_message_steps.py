from unittest.mock import MagicMock

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Skip, Success
from titan_cli.engine.context import WorkflowContext
from titan_plugin_slack.models import UISlackConversation, UISlackPostedMessage, UISlackTarget
from titan_plugin_slack.steps.message_steps import (
    format_blockkit_message_step,
    format_markdown_message_step,
    open_direct_message_step,
    prepare_message_destination_step,
    post_message_step,
    prompt_message_body_step,
)


def _build_context() -> WorkflowContext:
    ctx = WorkflowContext(secrets=MagicMock())
    ctx.textual = MagicMock()

    loading_mock = MagicMock()
    loading_mock.__enter__ = MagicMock(return_value=loading_mock)
    loading_mock.__exit__ = MagicMock(return_value=None)
    ctx.textual.loading = MagicMock(return_value=loading_mock)
    return ctx


def test_open_direct_message_step_requires_user_target() -> None:
    ctx = _build_context()
    ctx.slack = MagicMock()
    ctx.data["slack_target"] = UISlackTarget(
        target_type="channel",
        target_id="C123",
        target_name="general",
    )

    result = open_direct_message_step(ctx)

    assert isinstance(result, Error)
    assert result.message == "Direct messages require a Slack user target"


def test_open_direct_message_step_returns_conversation_metadata() -> None:
    ctx = _build_context()
    ctx.slack = MagicMock()
    ctx.data["slack_target"] = UISlackTarget(
        target_type="user",
        target_id="U123",
        target_name="Alex Smith",
    )
    conversation = UISlackConversation(id="D123", is_im=True, user_id="U123", team_id="T1")
    ctx.slack.open_direct_message.return_value = ClientSuccess(data=conversation)

    result = open_direct_message_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["slack_conversation"] == conversation
    assert result.metadata["slack_conversation_id"] == "D123"


def test_prepare_message_destination_step_uses_channel_target_directly() -> None:
    ctx = _build_context()
    ctx.slack = MagicMock()
    ctx.data["slack_target"] = UISlackTarget(
        target_type="channel",
        target_id="C123",
        target_name="general",
        team_id="T1",
    )

    result = prepare_message_destination_step(ctx)

    assert isinstance(result, Success)
    conversation = result.metadata["slack_conversation"]
    assert conversation.id == "C123"
    assert conversation.is_im is False


def test_prompt_message_body_step_skips_when_text_already_present() -> None:
    ctx = _build_context()
    ctx.data["slack_message_text"] = "Hello"

    result = prompt_message_body_step(ctx)

    assert isinstance(result, Skip)
    ctx.textual.ask_multiline.assert_not_called()


def test_prompt_message_body_step_skips_when_markdown_already_present() -> None:
    ctx = _build_context()
    ctx.data["slack_message_markdown"] = "**Hello**"

    result = prompt_message_body_step(ctx)

    assert isinstance(result, Skip)
    ctx.textual.ask_multiline.assert_not_called()


def test_prompt_message_body_step_returns_message_markdown() -> None:
    ctx = _build_context()
    ctx.textual.ask_multiline.return_value = "Hello there"

    result = prompt_message_body_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata == {"slack_message_markdown": "Hello there"}


def test_post_message_step_returns_message_metadata() -> None:
    ctx = _build_context()
    ctx.slack = MagicMock()
    ctx.data["slack_conversation_id"] = "D123"
    ctx.data["slack_message_text"] = "Hello there"
    posted = UISlackPostedMessage(channel="D123", ts="123.456", text="Hello there")
    ctx.slack.post_message.return_value = ClientSuccess(data=posted)

    result = post_message_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["slack_message"] == posted
    assert result.metadata["slack_message_ts"] == "123.456"
    assert result.metadata["slack_message_channel"] == "D123"


def test_post_message_step_returns_error_from_client() -> None:
    ctx = _build_context()
    ctx.slack = MagicMock()
    ctx.data["slack_conversation_id"] = "D123"
    ctx.data["slack_message_text"] = "Hello there"
    ctx.slack.post_message.return_value = ClientError(
        error_message="Slack post_message failed: missing_scope",
        error_code="POST_MESSAGE_ERROR",
    )

    result = post_message_step(ctx)

    assert isinstance(result, Error)
    assert result.message == "Slack post_message failed: missing_scope"


def test_format_markdown_message_step_skips_when_text_already_present() -> None:
    ctx = _build_context()
    ctx.data["slack_message_text"] = "Already ready: *bold*"
    ctx.data["slack_message_markdown"] = "**should be ignored**"

    result = format_markdown_message_step(ctx)

    assert isinstance(result, Skip)
    assert ctx.data["slack_message_text"] == "Already ready: *bold*"


def test_format_markdown_message_step_converts_markdown() -> None:
    ctx = _build_context()
    ctx.data["slack_message_markdown"] = "**bold** and a [link](https://example.com)"

    result = format_markdown_message_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["slack_message_text"] == "*bold* and a <https://example.com|link>"


def test_format_markdown_message_step_skips_when_nothing_provided() -> None:
    ctx = _build_context()

    result = format_markdown_message_step(ctx)

    assert isinstance(result, Skip)
    assert "slack_message_text" not in ctx.data


def test_format_blockkit_message_step_skips_when_blocks_already_present() -> None:
    ctx = _build_context()
    ctx.data["slack_message_blocks"] = [{"type": "divider"}]
    ctx.data["slack_message_markdown"] = "**should be ignored**"

    result = format_blockkit_message_step(ctx)

    assert isinstance(result, Skip)
    assert ctx.data["slack_message_blocks"] == [{"type": "divider"}]


def test_format_blockkit_message_step_converts_markdown() -> None:
    ctx = _build_context()
    ctx.data["slack_message_markdown"] = "# Release 0.7.0\n\nBody text."

    result = format_blockkit_message_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["slack_message_blocks"] == [
        {"type": "header", "text": {"type": "plain_text", "text": "Release 0.7.0"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "Body text."}},
    ]
    assert result.metadata["slack_message_text"] == "*Release 0.7.0*\n\nBody text."


def test_format_blockkit_message_step_keeps_existing_text_fallback() -> None:
    ctx = _build_context()
    ctx.data["slack_message_markdown"] = "# Release 0.7.0"
    ctx.data["slack_message_text"] = "Custom fallback"

    result = format_blockkit_message_step(ctx)

    assert isinstance(result, Success)
    assert "slack_message_text" not in result.metadata


def test_format_blockkit_message_step_skips_when_nothing_provided() -> None:
    ctx = _build_context()

    result = format_blockkit_message_step(ctx)

    assert isinstance(result, Skip)
    assert "slack_message_blocks" not in ctx.data


def test_post_message_step_forwards_blocks_to_client() -> None:
    ctx = _build_context()
    ctx.slack = MagicMock()
    ctx.data["slack_conversation_id"] = "D123"
    ctx.data["slack_message_text"] = "Hello there"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Hello there"}}]
    ctx.data["slack_message_blocks"] = blocks
    posted = UISlackPostedMessage(channel="D123", ts="123.456", text="Hello there")
    ctx.slack.post_message.return_value = ClientSuccess(data=posted)

    result = post_message_step(ctx)

    assert isinstance(result, Success)
    ctx.slack.post_message.assert_called_once_with(
        "D123", "Hello there", blocks=blocks, thread_ts=None
    )
