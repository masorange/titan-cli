from unittest.mock import MagicMock

import pytest

from titan_plugin_slack.plugin import SlackPlugin
from titan_plugin_slack.exceptions import SlackConfigurationError


def test_slack_plugin_basic_properties() -> None:
    plugin = SlackPlugin()

    assert plugin.name == "slack"
    assert plugin.description == "Provides Slack messaging and workspace integration."
    assert plugin.dependencies == []


def test_slack_plugin_exposes_public_steps() -> None:
    plugin = SlackPlugin()

    steps = plugin.get_steps()

    assert set(steps) == {
        "validate_connection",
        "list_public_channels",
        "list_users",
        "select_user_target",
        "select_channel_target",
        "select_default_or_search_channel_target",
        "select_target",
        "prepare_message_destination",
        "ensure_target_conversation",
        "read_recent_messages",
        "ai_summarize_messages",
        "open_direct_message",
        "prompt_message_body",
        "post_message",
    }


def test_slack_plugin_exposes_workflows_path() -> None:
    plugin = SlackPlugin()

    assert plugin.workflows_path.name == "workflows"


def test_slack_plugin_exposes_config_schema() -> None:
    plugin = SlackPlugin()

    schema = plugin.get_config_schema()

    assert "user_token" in schema["properties"]
    assert schema["properties"]["default_team_id"]["config_scope"] == "project"
    assert schema["properties"]["default_channels"]["config_scope"] == "project"


def test_slack_plugin_initialize_requires_user_token() -> None:
    plugin = SlackPlugin()
    config = MagicMock()
    config.config.plugins = {"slack": MagicMock(config={"oauth_client_id": "123"})}
    config.get_project_name.return_value = "demo-project"
    secrets = MagicMock()
    secrets.get.return_value = None

    with pytest.raises(SlackConfigurationError):
        plugin.initialize(config, secrets)


def test_slack_plugin_initialize_uses_personal_token() -> None:
    plugin = SlackPlugin()
    config = MagicMock()
    config.config.plugins = {
        "slack": MagicMock(config={"default_team_id": "T123"})
    }
    config.get_project_name.return_value = "demo-project"
    secrets = MagicMock()
    secrets.get.return_value = "xoxp-user-token"

    plugin.initialize(config, secrets)

    client = plugin.get_client()
    assert client.user_token == "xoxp-user-token"
    assert client.team_id == "T123"
    assert client.timeout == 30
    secrets.get.assert_called_once_with("demo-project_slack_user_token")
