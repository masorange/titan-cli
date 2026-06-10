from dataclasses import dataclass
import asyncio

import tomli
import tomli_w
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Input

from titan_cli.ui.tui.icons import Icons
from titan_cli.ui.tui.widgets import BoldPrimaryText, BoldText, Button, DimText, Text
from titan_cli.ui.tui.screens.base import BaseScreen

from ..clients.slack_client import SlackClient
from ..oauth import DEFAULT_SCOPES, SlackOAuthFlow, SlackOAuthResult


@dataclass
class SlackConnectionState:
    """Current Slack connection state for the active user."""

    has_token: bool
    oauth_client_id: str | None
    has_oauth_client_secret: bool
    oauth_redirect_port: int
    default_team_id: str | None
    default_team_name: str | None
    granted_scopes: list[str]
    auth_mode: str
    timeout: int


class SlackConfigScreen(BaseScreen):
    """Slack-specific configuration screen."""

    CSS = """
    SlackConfigScreen {
        align: center middle;
    }

    #slack-config-container {
        width: 100%;
        height: 1fr;
        background: $surface-lighten-1;
        padding: 0 2 1 2;
    }

    #slack-config-panel {
        width: 100%;
        height: 1fr;
        border: round $primary;
        border-title-align: center;
        background: $surface-lighten-1;
        padding: 0;
        layout: vertical;
    }

    #slack-config-scroll {
        height: 1fr;
    }

    #slack-config-body {
        padding: 1;
        height: auto;
    }

    #slack-config-buttons {
        height: auto;
        padding: 1 2;
        background: $surface-lighten-1;
        border-top: solid $primary;
        align: right middle;
    }

    #slack-config-buttons Button {
        margin-left: 1;
    }

    Input {
        width: 100%;
        margin-top: 1;
        margin-bottom: 1;
        border: solid $accent;
    }

    Input:focus {
        border: solid $primary;
    }
    """

    def __init__(self, config):
        super().__init__(
            config,
            title=f"{Icons.SETTINGS} Configure Slack",
            show_back=True,
            show_status_bar=False,
        )

    def compose_content(self) -> ComposeResult:
        with Container(id="slack-config-container"):
            panel = Container(id="slack-config-panel")
            panel.border_title = "Slack Connection"
            with panel:
                with VerticalScroll(id="slack-config-scroll"):
                    yield Container(id="slack-config-body")

                with Horizontal(id="slack-config-buttons"):
                    yield Button("Connect Slack", variant="primary", id="connect-button")
                    yield Button("Validate Connection", variant="default", id="validate-button")
                    yield Button("Disconnect", variant="error", id="disconnect-button")
                    yield Button("Close", variant="default", id="close-button")

    def on_mount(self) -> None:
        self._refresh_view()

    def _load_plugin_config(self) -> dict:
        plugin_cfg = getattr(self.config.config, "plugins", {}).get("slack") if self.config.config else None
        if not plugin_cfg:
            return {}
        return plugin_cfg.config if hasattr(plugin_cfg, "config") else {}

    def _has_user_token(self) -> bool:
        return bool(self.config.secrets.get("slack_user_token"))

    def _get_connection_state(self) -> SlackConnectionState:
        plugin_config = self._load_plugin_config()
        return SlackConnectionState(
            has_token=self._has_user_token(),
            oauth_client_id=plugin_config.get("oauth_client_id"),
            has_oauth_client_secret=bool(self.config.secrets.get("slack_oauth_client_secret")),
            oauth_redirect_port=plugin_config.get("oauth_redirect_port", 8765),
            default_team_id=plugin_config.get("default_team_id"),
            default_team_name=plugin_config.get("default_team_name"),
            granted_scopes=plugin_config.get("granted_scopes", []),
            auth_mode=plugin_config.get("auth_mode", "user_token"),
            timeout=plugin_config.get("timeout", 30),
        )

    def _save_global_slack_config(self, updates: dict[str, object | None]) -> None:
        global_cfg_path = self.config._global_config_path
        config_data = {}
        if global_cfg_path.exists():
            with open(global_cfg_path, "rb") as f:
                config_data = tomli.load(f)

        config_data.setdefault("config_version", getattr(self.config.config, "config_version", "1.0"))
        plugins = config_data.setdefault("plugins", {})
        plugin_table = plugins.setdefault("slack", {})
        plugin_config = plugin_table.setdefault("config", {})

        for key, value in updates.items():
            if value is None:
                plugin_config.pop(key, None)
            else:
                plugin_config[key] = value

        with open(global_cfg_path, "wb") as f:
            tomli_w.dump(config_data, f)

        self.config.load()

    def _refresh_view(self) -> None:
        state = self._get_connection_state()
        try:
            body = self.query_one("#slack-config-body", Container)
        except NoMatches:
            return
        body.remove_children()

        body.mount(BoldPrimaryText("Connect your personal Slack account"))
        body.mount(Text(""))
        body.mount(DimText("Slack uses a personal user token stored securely in your keyring."))
        body.mount(DimText("The primary configuration path for Slack uses a browser-based OAuth flow."))
        body.mount(Text(""))

        status_label = "Connected" if state.has_token else "Not connected"
        body.mount(BoldText("Current Status"))
        body.mount(DimText(f"  Status: {status_label}"))
        body.mount(DimText(f"  Auth Mode: {state.auth_mode}"))
        body.mount(DimText(f"  Timeout: {state.timeout}s"))
        body.mount(DimText(f"  OAuth Client ID: {state.oauth_client_id or 'Not set'}"))
        body.mount(DimText(f"  OAuth Client Secret: {'Stored' if state.has_oauth_client_secret else 'Not set'}"))
        body.mount(DimText(f"  OAuth Redirect Port: {state.oauth_redirect_port}"))
        body.mount(DimText(f"  Team ID: {state.default_team_id or 'Not set'}"))
        body.mount(DimText(f"  Team Name: {state.default_team_name or 'Not set'}"))
        scopes = ", ".join(state.granted_scopes) if state.granted_scopes else "Not recorded"
        body.mount(DimText(f"  Granted Scopes: {scopes}"))
        body.mount(Text(""))

        body.mount(BoldText("OAuth App Configuration"))
        body.mount(DimText("Client ID"))
        body.mount(Input(value=state.oauth_client_id or "", id="oauth-client-id-input"))
        body.mount(DimText("Client Secret"))
        body.mount(Input(value="", id="oauth-client-secret-input", password=True))
        body.mount(DimText("Redirect Port"))
        body.mount(Input(value=str(state.oauth_redirect_port), id="oauth-redirect-port-input"))
        body.mount(Text(""))

        body.mount(BoldText("Slack MVP0 Scopes"))
        for scope in DEFAULT_SCOPES:
            body.mount(DimText(f"  {scope}"))
        body.mount(Text(""))
        body.mount(DimText("Use Connect Slack to open the browser-based Slack OAuth flow."))

        self.query_one("#validate-button", Button).disabled = not state.has_token
        self.query_one("#disconnect-button", Button).disabled = not state.has_token

    def _read_oauth_form_values(self) -> tuple[str, str, int]:
        """Read and validate the OAuth app form values from the screen."""
        client_id = self.query_one("#oauth-client-id-input", Input).value.strip()
        client_secret_input = self.query_one("#oauth-client-secret-input", Input).value.strip()
        redirect_port_raw = self.query_one("#oauth-redirect-port-input", Input).value.strip() or "8765"

        if not client_id:
            raise ValueError("Slack OAuth client ID is required.")

        try:
            redirect_port = int(redirect_port_raw)
        except ValueError as exc:
            raise ValueError("Slack OAuth redirect port must be a number.") from exc

        if redirect_port <= 0:
            raise ValueError("Slack OAuth redirect port must be greater than zero.")

        client_secret = client_secret_input or self.config.secrets.get("slack_oauth_client_secret")
        if not client_secret:
            raise ValueError("Slack OAuth client secret is required.")

        return client_id, client_secret, redirect_port

    def _save_oauth_app_config(self, client_id: str, client_secret: str, redirect_port: int) -> None:
        """Persist OAuth app settings for Slack."""
        timeout = self._load_plugin_config().get("timeout", 30)
        self.config.secrets.set("slack_oauth_client_secret", client_secret, scope="user")
        self._save_global_slack_config(
            {
                "oauth_client_id": client_id,
                "oauth_redirect_port": redirect_port,
                "timeout": timeout,
                "auth_mode": "user_token",
            }
        )

    def _perform_oauth_connect(self, client_id: str, client_secret: str, redirect_port: int) -> SlackOAuthResult:
        """Run the synchronous Slack OAuth backend flow."""
        flow = SlackOAuthFlow(
            client_id=client_id,
            client_secret=client_secret,
            redirect_port=redirect_port,
        )
        return flow.run()

    def _start_oauth_flow(self) -> None:
        """Start the Slack OAuth flow in a background worker."""
        try:
            client_id, client_secret, redirect_port = self._read_oauth_form_values()
            self._save_oauth_app_config(client_id, client_secret, redirect_port)
        except Exception as exc:
            self.app.notify(f"Slack OAuth setup failed: {exc}", severity="error")
            return

        self.app.notify("Opening browser for Slack authorization...", severity="information")
        self.run_worker(
            self._run_oauth_connect(client_id, client_secret, redirect_port),
            exclusive=True,
        )

    async def _run_oauth_connect(self, client_id: str, client_secret: str, redirect_port: int) -> None:
        """Run the Slack OAuth flow without blocking the UI thread."""
        try:
            result = await asyncio.to_thread(
                self._perform_oauth_connect,
                client_id,
                client_secret,
                redirect_port,
            )
            self.config.secrets.set("slack_user_token", result.access_token, scope="user")
            self._save_global_slack_config(
                {
                    "oauth_client_id": client_id,
                    "oauth_redirect_port": redirect_port,
                    "default_team_id": result.team_id,
                    "default_team_name": result.team_name,
                    "granted_scopes": result.granted_scopes,
                    "auth_mode": "user_token",
                }
            )
            self.app.notify("Slack connected successfully.", severity="information")
            self._refresh_view()
        except Exception as exc:
            self.app.notify(f"Slack OAuth failed: {exc}", severity="error")

    def _validate_connection(self) -> None:
        plugin_config = self._load_plugin_config()
        client = SlackClient(
            user_token=self.config.secrets.get("slack_user_token") or "",
            team_id=plugin_config.get("default_team_id"),
            timeout=plugin_config.get("timeout", 30),
        )
        result = client.auth_test()

        self._save_global_slack_config(
            {
                "default_team_id": result.get("team_id"),
                "default_team_name": result.get("team"),
                "auth_mode": "user_token",
                "timeout": plugin_config.get("timeout", 30),
            }
        )
        self.app.notify("Slack connection validated successfully.", severity="information")
        self._refresh_view()

    def _disconnect(self) -> None:
        self.config.secrets.delete("slack_user_token", scope="user")
        self._save_global_slack_config(
            {
                "default_team_id": None,
                "default_team_name": None,
                "granted_scopes": None,
            }
        )
        self.app.notify("Slack connection removed.", severity="information")
        self._refresh_view()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect-button":
            self._start_oauth_flow()
        elif event.button.id == "validate-button":
            try:
                self._validate_connection()
            except Exception as exc:
                self.app.notify(f"Slack validation failed: {exc}", severity="error")
        elif event.button.id == "disconnect-button":
            try:
                self._disconnect()
            except Exception as exc:
                self.app.notify(f"Failed to remove Slack connection: {exc}", severity="error")
        elif event.button.id == "close-button":
            self.dismiss(result=False)
