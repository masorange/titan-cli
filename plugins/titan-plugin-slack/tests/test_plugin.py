from unittest.mock import MagicMock

import pytest

from titan_plugin_slack.plugin import SlackPlugin
from titan_plugin_slack.exceptions import SlackConfigurationError


def test_slack_plugin_basic_properties() -> None:
    plugin = SlackPlugin()

    assert plugin.name == "slack"
    assert plugin.description == "Provides Slack messaging and workspace integration."
    assert plugin.dependencies == []


def test_slack_plugin_has_no_steps_in_phase_one() -> None:
    plugin = SlackPlugin()

    assert plugin.get_steps() == {}


def test_slack_plugin_exposes_workflows_path() -> None:
    plugin = SlackPlugin()

    assert plugin.workflows_path.name == "workflows"


def test_slack_plugin_exposes_config_schema() -> None:
    plugin = SlackPlugin()

    schema = plugin.get_config_schema()

    assert "user_token" in schema["properties"]
    assert schema["properties"]["default_team_id"]["config_scope"] == "global"
    assert schema["properties"]["auth_mode"]["default"] == "user_token"


def test_slack_plugin_initialize_requires_user_token() -> None:
    plugin = SlackPlugin()
    config = MagicMock()
    config.config.plugins = {}
    secrets = MagicMock()
    secrets.get.return_value = None

    with pytest.raises(SlackConfigurationError):
        plugin.initialize(config, secrets)


def test_slack_plugin_initialize_uses_personal_token() -> None:
    plugin = SlackPlugin()
    config = MagicMock()
    config.config.plugins = {
        "slack": MagicMock(config={"default_team_id": "T123", "timeout": 45})
    }
    secrets = MagicMock()
    secrets.get.return_value = "xoxp-user-token"

    plugin.initialize(config, secrets)

    client = plugin.get_client()
    assert client.user_token == "xoxp-user-token"
    assert client.team_id == "T123"
    assert client.timeout == 45
