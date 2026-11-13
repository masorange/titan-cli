import json
import time
from unittest.mock import MagicMock

import requests

import pytest

from titan_plugin_slack.plugin import SlackPlugin
from titan_plugin_slack.exceptions import SlackConfigurationError


class FakeBroker:
    """Dict-backed stand-in honoring the SecretBroker surface plugins use."""

    namespace = "titan.plugins.slack"

    def __init__(self, values=None):
        self.values = dict(values or {})
        self.stored = {}

    def exists(self, key):
        return self.values.get(key) is not None

    def store(self, key, value):
        self.values[key] = value
        self.stored[key] = value

    def delete(self, key):
        self.values.pop(key, None)

    def create_client(self, key, builder, required=True):
        value = self.values.get(key)
        if value is None and required:
            raise KeyError(key)
        return builder(value)


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
        "format_markdown_message",
        "prompt_message_body",
        "post_message",
        "upload_file",
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


def _grant(access: str, refresh: str | None = None, expires_at: int | None = None) -> str:
    return json.dumps(
        {"access_token": access, "refresh_token": refresh, "expires_at": expires_at, "scopes": []}
    )


def _config(plugin_config: dict) -> MagicMock:
    config = MagicMock()
    config.get_project_name.return_value = "demo-project"
    config.config.plugins = {"slack": MagicMock(config=plugin_config)}
    return config


def test_slack_plugin_initialize_requires_user_token() -> None:
    plugin = SlackPlugin()

    with pytest.raises(SlackConfigurationError, match="Slack user token not found"):
        plugin.initialize(_config({"oauth_client_id": "123"}), FakeBroker())


def test_slack_plugin_initialize_uses_personal_token() -> None:
    plugin = SlackPlugin()
    broker = FakeBroker({"demo-project_slack_oauth": _grant("xoxp-user-token")})

    plugin.initialize(_config({"oauth_client_id": "123", "default_team_id": "T1"}), broker)

    client = plugin.get_client()
    assert client.user_token == "xoxp-user-token"
    assert client.team_id == "T1"
    # A token without expiry is used as is: nothing refreshed, nothing written.
    assert broker.stored == {}


def test_slack_plugin_initialize_refreshes_expiring_token(monkeypatch) -> None:
    plugin = SlackPlugin()
    broker = FakeBroker(
        {"demo-project_slack_oauth": _grant("xoxe-old", "xoxe-old-refresh", int(time.time()) + 10)}
    )
    posted = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        posted.update(data)
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(
            {"ok": True, "access_token": "xoxe-new", "refresh_token": "xoxe-new-refresh", "expires_in": 43200}
        ).encode()
        return response

    monkeypatch.setattr(requests, "post", fake_post)

    plugin.initialize(_config({"oauth_client_id": "123"}), broker)

    assert posted["refresh_token"] == "xoxe-old-refresh"
    assert posted["client_id"] == "123"
    assert plugin.get_client().user_token == "xoxe-new"
    stored = json.loads(broker.stored["demo-project_slack_oauth"])
    assert stored["access_token"] == "xoxe-new"
    assert stored["refresh_token"] == "xoxe-new-refresh"
