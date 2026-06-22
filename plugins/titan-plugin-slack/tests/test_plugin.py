from pathlib import Path
from unittest.mock import MagicMock

import tomli

import pytest

from titan_plugin_slack.plugin import SlackPlugin
from titan_plugin_slack.exceptions import SlackConfigurationError
from titan_plugin_slack.oauth import SlackOAuthResult


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
    secrets.get.side_effect = ["xoxp-user-token", None, None]

    plugin.initialize(config, secrets)

    client = plugin.get_client()
    assert client.user_token == "xoxp-user-token"
    assert client.team_id == "T123"
    assert client.timeout == 30
    assert secrets.get.call_args_list[0].args == ("demo-project_slack_user_token",)
    assert secrets.get.call_args_list[1].args == ("demo-project_slack_refresh_token",)


def test_slack_plugin_initialize_refreshes_expiring_pkce_token(tmp_path: Path, monkeypatch) -> None:
    plugin = SlackPlugin()
    project_config_path = tmp_path / "project-config.toml"
    project_config_path.write_text(
        """
[plugins.slack]
enabled = true

[plugins.slack.config]
oauth_client_id = "123"
default_team_id = "T123"
default_team_name = "Acme"
granted_scopes = ["users:read"]
default_channels = ["general"]
""".strip()
    )

    config = MagicMock()
    config.project_config_path = project_config_path
    config.get_project_name.return_value = "demo-project"
    config.config = MagicMock()
    config.config.config_version = "1.0"
    config.config.plugins = {
        "slack": MagicMock(
            config={
                "oauth_client_id": "123",
                "default_team_id": "T123",
                "default_team_name": "Acme",
                "granted_scopes": ["users:read"],
                "default_channels": ["general"],
            }
        )
    }

    def fake_load() -> None:
        with open(project_config_path, "rb") as f:
            data = tomli.load(f)
        config.config.plugins = {
            "slack": MagicMock(config=data["plugins"]["slack"]["config"])
        }

    config.load = MagicMock(side_effect=fake_load)

    secrets = MagicMock()
    secrets.get.side_effect = ["xoxe-old-token", "xoxe-old-refresh-token", "1"]

    refreshed = SlackOAuthResult(
        access_token="xoxe-new-token",
        refresh_token="xoxe-new-refresh-token",
        expires_in=43200,
        token_type="Bearer",
        granted_scopes=["users:read", "channels:read"],
        team_id="T123",
        team_name="Acme",
        authed_user_id=None,
    )

    class FakeFlow:
        def __init__(self, client_id):
            self.client_id = client_id

        def refresh_access_token(self, refresh_token):
            assert refresh_token == "xoxe-old-refresh-token"
            return refreshed

    monkeypatch.setattr("titan_plugin_slack.plugin.SlackOAuthFlow", FakeFlow)

    plugin.initialize(config, secrets)

    client = plugin.get_client()
    assert client.user_token == "xoxe-new-token"
    secrets.set.assert_any_call("demo-project_slack_user_token", "xoxe-new-token", scope="user")
    secrets.set.assert_any_call(
        "demo-project_slack_refresh_token", "xoxe-new-refresh-token", scope="user"
    )
    expires_at_call = next(
        call for call in secrets.set.call_args_list if call.args[0] == "demo-project_slack_token_expires_at"
    )
    assert expires_at_call.kwargs["scope"] == "user"
