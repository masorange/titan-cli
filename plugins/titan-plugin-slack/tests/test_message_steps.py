from unittest.mock import MagicMock

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Skip, Success
from titan_cli.engine.context import WorkflowContext
from titan_plugin_slack.models import UISlackConversation, UISlackPostedMessage, UISlackTarget
from titan_plugin_slack.steps.message_steps import (
    open_direct_message_step,
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


def test_prompt_message_body_step_skips_when_preset_exists() -> None:
    ctx = _build_context()
    ctx.data["slack_message_text"] = "Hello"

    result = prompt_message_body_step(ctx)

    assert isinstance(result, Skip)
    assert result.metadata == {"slack_message_text": "Hello"}


def test_prompt_message_body_step_returns_message_text() -> None:
    ctx = _build_context()
    ctx.textual.ask_multiline.return_value = "Hello there"

    result = prompt_message_body_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata == {"slack_message_text": "Hello there"}


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
