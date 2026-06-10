from dataclasses import dataclass
import asyncio

import tomli
import tomli_w
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Input, Static

from titan_cli.ui.tui.icons import Icons
from titan_cli.ui.tui.widgets import BoldPrimaryText, BoldText, Button, DimText, Text
from titan_cli.ui.tui.screens.base import BaseScreen
from titan_cli.core.logging import get_logger

from titan_cli.core.result import ClientError, ClientSuccess

from ..clients.slack_client import SlackClient
from ..oauth import DEFAULT_SCOPES, SlackOAuthFlow, SlackOAuthResult


logger = get_logger(__name__)


@dataclass
class SlackConnectionState:
    """Current Slack connection state for the active user."""

    has_token: bool
    oauth_client_id: str | None
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

    .slack-section-title {
        margin-top: 1;
    }

    .slack-section-body {
        height: auto;
        margin-bottom: 1;
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
                    with Container(id="slack-config-body"):
                        yield BoldPrimaryText("Connect your personal Slack account", id="slack-title")
                        yield Text("")
                        yield Static(id="slack-intro")
                        yield Text("")

                        yield BoldText("Current Status", classes="slack-section-title")
                        yield Static(id="slack-status-block", classes="slack-section-body")

                        yield BoldText("OAuth App Configuration", classes="slack-section-title")
                        yield Static(id="slack-oauth-help", classes="slack-section-body")
                        yield DimText("Client ID")
                        yield Input(id="oauth-client-id-input")
                        yield DimText("Redirect Port")
                        yield Input(value="8765", id="oauth-redirect-port-input")
                        yield Text("")

                        yield BoldText("Slack MVP0 Scopes", classes="slack-section-title")
                        yield Static(id="slack-scopes-block", classes="slack-section-body")
                        yield Static(id="slack-connect-help", classes="slack-section-body")

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

    def _enable_plugin_for_current_project(self) -> None:
        """Ensure Slack is enabled in the current project's config."""
        project_cfg_path = self.config.project_config_path
        if not project_cfg_path:
            return

        project_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        project_data = {}
        if project_cfg_path.exists():
            with open(project_cfg_path, "rb") as f:
                project_data = tomli.load(f)

        plugins = project_data.setdefault("plugins", {})
        plugin_table = plugins.setdefault("slack", {})
        plugin_table["enabled"] = True

        with open(project_cfg_path, "wb") as f:
            tomli_w.dump(project_data, f)

        self.config.load()

    def _refresh_view(self) -> None:
        state = self._get_connection_state()
        try:
            intro = self.query_one("#slack-intro", Static)
            status_block = self.query_one("#slack-status-block", Static)
            oauth_help = self.query_one("#slack-oauth-help", Static)
            scopes_block = self.query_one("#slack-scopes-block", Static)
            connect_help = self.query_one("#slack-connect-help", Static)
            client_id_input = self.query_one("#oauth-client-id-input", Input)
            redirect_port_input = self.query_one("#oauth-redirect-port-input", Input)
        except NoMatches:
            return

        status_label = "Connected" if state.has_token else "Not connected"
        scopes = ", ".join(state.granted_scopes) if state.granted_scopes else "Not recorded"

        intro.update(
            "Slack uses a personal user token stored securely in your keyring.\n"
            "The primary configuration path for Slack uses a browser-based OAuth flow."
        )
        status_block.update(
            f"  Status: {status_label}\n"
            f"  Auth Mode: {state.auth_mode}\n"
            f"  Timeout: {state.timeout}s\n"
            f"  OAuth Client ID: {state.oauth_client_id or 'Not set'}\n"
            f"  OAuth Redirect Port: {state.oauth_redirect_port}\n"
            f"  Team ID: {state.default_team_id or 'Not set'}\n"
            f"  Team Name: {state.default_team_name or 'Not set'}\n"
            f"  Granted Scopes: {scopes}"
        )
        oauth_help.update(
            "Titan will open Slack in your browser and complete the OAuth PKCE flow.\n"
            "Create your own Slack App, enable PKCE, and configure this exact redirect URL in Slack OAuth settings:\n"
            f"  {self._build_redirect_uri(state.oauth_redirect_port)}\n"
            "The redirect URL in Slack must match exactly, including host, port, and path.\n"
            "For example, `127.0.0.1` and `localhost` are different values for Slack."
        )
        scopes_block.update("\n".join(f"  {scope}" for scope in DEFAULT_SCOPES))
        connect_help.update("Use Connect Slack to open the browser-based Slack OAuth flow.")

        client_id_input.value = state.oauth_client_id or ""
        redirect_port_input.value = str(state.oauth_redirect_port)

        self.query_one("#validate-button", Button).disabled = not state.has_token
        self.query_one("#disconnect-button", Button).disabled = not state.has_token

    @staticmethod
    def _build_redirect_uri(port: int) -> str:
        """Build the localhost redirect URI shown to the user."""
        return f"http://127.0.0.1:{port}/slack/callback"

    def _read_oauth_form_values(self) -> tuple[str, int]:
        """Read and validate the OAuth app form values from the screen."""
        client_id = self.query_one("#oauth-client-id-input", Input).value.strip()
        redirect_port_raw = self.query_one("#oauth-redirect-port-input", Input).value.strip() or "8765"

        if not client_id:
            raise ValueError("Slack OAuth client ID is required.")

        try:
            redirect_port = int(redirect_port_raw)
        except ValueError as exc:
            raise ValueError("Slack OAuth redirect port must be a number.") from exc

        if redirect_port <= 0:
            raise ValueError("Slack OAuth redirect port must be greater than zero.")

        return client_id, redirect_port

    def _save_oauth_app_config(self, client_id: str, redirect_port: int) -> None:
        """Persist OAuth app settings for Slack."""
        timeout = self._load_plugin_config().get("timeout", 30)
        self._save_global_slack_config(
            {
                "oauth_client_id": client_id,
                "oauth_redirect_port": redirect_port,
                "timeout": timeout,
                "auth_mode": "user_token",
            }
        )

    def _perform_oauth_connect(self, client_id: str, redirect_port: int) -> SlackOAuthResult:
        """Run the synchronous Slack OAuth backend flow."""
        flow = SlackOAuthFlow(
            client_id=client_id,
            redirect_port=redirect_port,
        )
        return flow.run()

    def _start_oauth_flow(self) -> None:
        """Start the Slack OAuth flow in a background worker."""
        try:
            client_id, redirect_port = self._read_oauth_form_values()
            self._save_oauth_app_config(client_id, redirect_port)
        except Exception as exc:
            logger.exception("slack_oauth_setup_failed")
            self.app.notify(f"Slack OAuth setup failed: {exc}", severity="error")
            return

        self.app.notify("Opening browser for Slack authorization...", severity="information")
        self.run_worker(
            self._run_oauth_connect(client_id, redirect_port),
            exclusive=True,
        )

    async def _run_oauth_connect(self, client_id: str, redirect_port: int) -> None:
        """Run the Slack OAuth flow without blocking the UI thread."""
        try:
            result = await asyncio.to_thread(
                self._perform_oauth_connect,
                client_id,
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
            self._enable_plugin_for_current_project()
            self.app.notify("Slack connected successfully.", severity="information")
            self.dismiss(result=True)
        except Exception as exc:
            logger.exception("slack_oauth_run_failed")
            self.app.notify(f"Slack OAuth failed: {exc}", severity="error")

    def _validate_connection(self) -> None:
        plugin_config = self._load_plugin_config()
        client = SlackClient(
            user_token=self.config.secrets.get("slack_user_token") or "",
            team_id=plugin_config.get("default_team_id"),
            timeout=plugin_config.get("timeout", 30),
        )
        result = client.auth_test()

        match result:
            case ClientSuccess(data=auth):
                self._save_global_slack_config(
                    {
                        "default_team_id": auth.team_id,
                        "default_team_name": auth.team,
                        "auth_mode": "user_token",
                        "timeout": plugin_config.get("timeout", 30),
                    }
                )
                self._enable_plugin_for_current_project()
                self.app.notify(
                    "Slack connection validated successfully.", severity="information"
                )
                self.dismiss(result=True)
            case ClientError(error_message=err):
                raise RuntimeError(err)

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
