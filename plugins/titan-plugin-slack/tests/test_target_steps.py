from unittest.mock import MagicMock

from titan_cli.core.result import ClientSuccess
from titan_cli.engine import Error, Success
from titan_cli.engine.context import WorkflowContext
from titan_plugin_slack.models import UISlackChannel, UISlackTarget, UISlackUser
from titan_plugin_slack.steps.target_steps import (
    select_channel_target_step,
    select_user_target_step,
)


def _build_context() -> WorkflowContext:
    ctx = WorkflowContext(secrets=MagicMock())
    ctx.textual = MagicMock()
    return ctx


def test_select_user_target_returns_error_without_source_users() -> None:
    ctx = _build_context()
    ctx.slack = MagicMock()
    ctx.textual.ask_text.return_value = "alex"
    ctx.slack.search_users.return_value = ClientSuccess(data=[])

    result = select_user_target_step(ctx)

    assert isinstance(result, Error)
    assert result.message == "No Slack users matched that query."


def test_select_user_target_returns_target_metadata() -> None:
    ctx = _build_context()
    ctx.slack = MagicMock()
    ctx.data["slack_team_id"] = "T1"
    ctx.textual.ask_text.return_value = "alex"
    user = UISlackUser(id="U1", name="alex", real_name="Alex Smith")
    ctx.slack.search_users.return_value = ClientSuccess(data=[user])
    ctx.textual.ask_option.return_value = user

    result = select_user_target_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["slack_target"] == UISlackTarget(
        target_type="user",
        target_id="U1",
        target_name="Alex Smith",
        team_id="T1",
        connection_id=None,
    )
    assert result.metadata["slack_target_type"] == "user"
    assert result.metadata["slack_target_id"] == "U1"
    assert result.metadata["slack_target_name"] == "Alex Smith"


def test_select_channel_target_returns_error_for_short_query() -> None:
    ctx = _build_context()
    ctx.slack = MagicMock()
    ctx.textual.ask_text.return_value = "g"

    result = select_channel_target_step(ctx)

    assert isinstance(result, Error)
    assert result.message == "Enter at least 2 characters to search Slack channels."


def test_select_channel_target_returns_target_metadata() -> None:
    ctx = _build_context()
    ctx.slack = MagicMock()
    ctx.textual.ask_text.return_value = "eng"
    channel = UISlackChannel(id="C2", name="eng-backend")
    ctx.slack.search_channels.return_value = ClientSuccess(data=[channel])
    ctx.textual.ask_option.return_value = channel

    result = select_channel_target_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["slack_target"] == UISlackTarget(
        target_type="channel",
        target_id="C2",
        target_name="eng-backend",
        team_id=None,
        connection_id=None,
    )
    assert result.metadata["slack_target_type"] == "channel"
    assert result.metadata["slack_target_id"] == "C2"
    assert result.metadata["slack_target_name"] == "eng-backend"
