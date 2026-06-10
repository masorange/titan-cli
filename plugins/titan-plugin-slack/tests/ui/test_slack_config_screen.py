from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import tomli

from titan_plugin_slack.plugin import SlackPlugin
from titan_plugin_slack.screens.slack_config_screen import SlackConfigScreen


def _build_config(tmp_path: Path, token: str | None = None, plugin_config: dict | None = None):
    config = MagicMock()
    config._global_config_path = tmp_path / "config.toml"
    config.config = MagicMock()
    config.config.config_version = "1.0"
    config.config.plugins = {}
    if plugin_config is not None:
        config.config.plugins["slack"] = MagicMock(config=plugin_config)

    secrets = MagicMock()
    secrets.get.return_value = token
    config.secrets = secrets
    config.load = MagicMock()
    return config


def test_slack_plugin_returns_custom_config_screen(tmp_path: Path) -> None:
    plugin = SlackPlugin()
    config = _build_config(tmp_path)

    assert plugin.has_custom_config_screen() is True
    assert isinstance(plugin.create_config_screen(config), SlackConfigScreen)


def test_slack_config_screen_reports_connection_state(tmp_path: Path) -> None:
    config = _build_config(
        tmp_path,
        token="xoxp-token",
        plugin_config={
            "default_team_id": "T123",
            "default_team_name": "Acme",
            "granted_scopes": ["users:read", "channels:read"],
            "auth_mode": "user_token",
            "timeout": 45,
        },
    )
    screen = SlackConfigScreen(config)

    state = screen._get_connection_state()

    assert state.has_token is True
    assert state.default_team_id == "T123"
    assert state.default_team_name == "Acme"
    assert state.granted_scopes == ["users:read", "channels:read"]
    assert state.timeout == 45


def test_slack_config_screen_disconnect_clears_token_and_metadata(tmp_path: Path) -> None:
    config = _build_config(tmp_path, token="xoxp-token")
    screen = SlackConfigScreen(config)

    app = MagicMock()
    type(screen).app = PropertyMock(return_value=app)

    screen._save_global_slack_config(
        {
            "default_team_id": "T123",
            "default_team_name": "Acme",
            "granted_scopes": ["users:read"],
            "auth_mode": "user_token",
            "timeout": 30,
        }
    )
    screen._disconnect()

    config.secrets.delete.assert_called_once_with("slack_user_token", scope="user")
    with open(config._global_config_path, "rb") as f:
        data = tomli.load(f)

    slack_cfg = data["plugins"]["slack"]["config"]
    assert "default_team_id" not in slack_cfg
    assert "default_team_name" not in slack_cfg
    assert "granted_scopes" not in slack_cfg
    assert slack_cfg["auth_mode"] == "user_token"
    assert slack_cfg["timeout"] == 30


def test_slack_config_screen_connect_shows_oauth_placeholder(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    screen = SlackConfigScreen(config)

    app = MagicMock()
    type(screen).app = PropertyMock(return_value=app)

    screen._start_oauth_flow()

    app.notify.assert_called_once_with(
        "Slack OAuth flow will be implemented in the next step.",
        severity="information",
    )
