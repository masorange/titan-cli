from pathlib import Path
import asyncio
from unittest.mock import MagicMock, PropertyMock

import tomli

from titan_plugin_slack.plugin import SlackPlugin
from titan_cli.core.security import OAuthGrant
from titan_plugin_slack.screens.slack_config_screen import SlackConfigScreen


class FakeBroker:
    """Dict-backed stand-in honoring the SecretBroker surface the screen uses."""

    def __init__(self, values=None):
        self.values = dict(values or {})
        self.stored = {}
        self.deleted = []
        self.store_error = None

    def exists(self, key):
        return self.values.get(key) is not None

    def store(self, key, value):
        if self.store_error is not None:
            raise self.store_error
        self.values[key] = value
        self.stored[key] = value

    def delete(self, key):
        self.deleted.append(key)
        self.values.pop(key, None)

    def create_client(self, key, builder, required=True):
        value = self.values.get(key)
        if value is None and required:
            raise KeyError(key)
        return builder(value)


def _build_config(tmp_path: Path, token: str | None = None, plugin_config: dict | None = None):
    config = MagicMock()
    config._global_config_path = tmp_path / "config.toml"
    config.project_config_path = tmp_path / "project-config.toml"
    config.get_project_name.return_value = "demo-project"
    config.config = MagicMock()
    config.config.config_version = "1.0"
    config.config.plugins = {}
    if plugin_config is not None:
        config.config.plugins["slack"] = MagicMock(config=plugin_config)

    broker = FakeBroker(
        {"demo-project_slack_oauth": token} if token else {}
    )
    config.broker = broker
    config.broker_factory = MagicMock()
    config.broker_factory.for_plugin.return_value = broker
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
            "oauth_client_id": "123",
            "default_team_id": "T123",
            "default_team_name": "Acme",
            "granted_scopes": ["users:read", "channels:read"],
            "default_channels": ["general", "release-notes"],
        },
    )
    screen = SlackConfigScreen(config)

    state = screen._get_connection_state()

    assert state.has_project_config is True
    assert state.has_token is True
    assert state.oauth_client_id == "123"
    assert state.default_team_id == "T123"
    assert state.default_team_name == "Acme"
    assert state.granted_scopes == ["users:read", "channels:read"]
    assert state.default_channels == ["general", "release-notes"]


def test_slack_config_screen_disconnect_only_deletes_project_token(tmp_path: Path) -> None:
    config = _build_config(tmp_path, token="xoxp-token")
    screen = SlackConfigScreen(config)

    app = MagicMock()
    type(screen).app = PropertyMock(return_value=app)

    screen._save_project_slack_config(
        {
            "oauth_client_id": "123",
            "default_team_id": "T123",
            "default_team_name": "Acme",
            "granted_scopes": ["users:read"],
            "default_channels": ["general"],
        }
    )
    screen._disconnect()

    assert config.broker.deleted == ["demo-project_slack_oauth"]
    with open(config.project_config_path, "rb") as f:
        data = tomli.load(f)

    assert data["plugins"]["slack"]["enabled"] is True
    assert data["plugins"]["slack"]["config"]["oauth_client_id"] == "123"


def test_slack_config_screen_remove_project_config_clears_plugin_entry_and_token(tmp_path: Path) -> None:
    config = _build_config(tmp_path, token="xoxp-token")
    screen = SlackConfigScreen(config)

    app = MagicMock()
    type(screen).app = PropertyMock(return_value=app)

    screen._save_project_slack_config(
        {
            "oauth_client_id": "123",
            "default_team_id": "T123",
            "default_team_name": "Acme",
            "granted_scopes": ["users:read"],
            "default_channels": ["general"],
        }
    )

    screen._remove_project_config()

    assert config.broker.deleted == ["demo-project_slack_oauth"]
    with open(config.project_config_path, "rb") as f:
        data = tomli.load(f)

    assert data.get("plugins", {}) == {}


def test_slack_config_screen_start_oauth_flow_runs_worker(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    screen = SlackConfigScreen(config)

    app = MagicMock()
    type(screen).app = PropertyMock(return_value=app)

    screen.run_worker = MagicMock()
    screen._read_oauth_form_values = MagicMock(return_value=("123", ["general"]))
    screen._save_oauth_app_config = MagicMock()

    screen._start_oauth_flow()

    app.notify.assert_called_once_with(
        "Opening browser for Slack authorization...",
        severity="information",
    )
    screen.run_worker.assert_called_once()
    worker_coro = screen.run_worker.call_args.args[0]
    worker_coro.close()


GRANT = OAuthGrant(
    scopes=("users:read",),
    expires_at=None,
    has_refresh_token=True,
    metadata={"team_id": "T123", "team_name": "Acme", "user_id": "U123"},
)


def test_slack_config_screen_perform_oauth_connect_uses_shared_flow(monkeypatch, tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    screen = SlackConfigScreen(config)
    calls = {}

    def fake_connect(broker, key, provider, app):
        calls.update(broker=broker, key=key, provider=provider, app=app)
        return GRANT

    monkeypatch.setattr(
        "titan_plugin_slack.screens.slack_config_screen.connect_oauth", fake_connect
    )

    assert screen._perform_oauth_connect("123") is GRANT
    assert calls["broker"] is config.broker
    assert calls["key"] == "demo-project_slack_oauth"
    assert calls["provider"].callback_path == "/slack/callback"
    assert calls["app"].client_id == "123"
    assert calls["app"].redirect_port == 8765


def test_slack_config_screen_oauth_connect_saves_team_from_grant(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    screen = SlackConfigScreen(config)
    type(screen).app = PropertyMock(return_value=MagicMock())
    screen.dismiss = MagicMock()
    screen._perform_oauth_connect = MagicMock(return_value=GRANT)

    asyncio.run(screen._run_oauth_connect("123", ["general"]))

    with open(config.project_config_path, "rb") as f:
        slack_cfg = tomli.load(f)["plugins"]["slack"]["config"]
    assert slack_cfg["default_team_id"] == "T123"
    assert slack_cfg["default_team_name"] == "Acme"
    assert slack_cfg["granted_scopes"] == ["users:read"]
    screen.dismiss.assert_called_once_with(result=True)


def test_slack_config_screen_saves_oauth_app_config(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    screen = SlackConfigScreen(config)

    screen._save_oauth_app_config("123", ["general", "release-notes"])

    with open(config.project_config_path, "rb") as f:
        data = tomli.load(f)

    slack_cfg = data["plugins"]["slack"]["config"]
    assert slack_cfg["oauth_client_id"] == "123"
    assert slack_cfg["default_channels"] == ["general", "release-notes"]
    assert data["plugins"]["slack"]["enabled"] is True


def test_slack_config_screen_oauth_connect_drops_grant_when_config_save_fails(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    screen = SlackConfigScreen(config)

    app = MagicMock()
    type(screen).app = PropertyMock(return_value=app)

    screen._perform_oauth_connect = MagicMock(return_value=GRANT)
    screen._save_project_slack_config = MagicMock(side_effect=RuntimeError("disk full"))

    asyncio.run(screen._run_oauth_connect("123", ["general"]))

    app.notify.assert_called_once_with("Slack OAuth failed: disk full", severity="error")
    assert config.broker.deleted == ["demo-project_slack_oauth"]


def test_slack_config_screen_save_project_config_enables_plugin(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    screen = SlackConfigScreen(config)

    screen._save_project_slack_config({"oauth_client_id": "123"})

    with open(config.project_config_path, "rb") as f:
        data = tomli.load(f)

    assert data["plugins"]["slack"]["enabled"] is True


def test_parse_default_channels_normalizes_and_deduplicates() -> None:
    result = SlackConfigScreen._parse_default_channels(
        "#general, release-notes, general,  ,\n#alerts"
    )

    assert result == ["general", "release-notes", "alerts"]
