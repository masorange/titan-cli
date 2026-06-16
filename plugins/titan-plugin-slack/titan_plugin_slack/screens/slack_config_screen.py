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
from ..config import build_project_slack_token_key
from ..oauth import SlackOAuthFlow, SlackOAuthResult


logger = get_logger(__name__)
DEFAULT_OAUTH_REDIRECT_PORT = 8765


@dataclass
class SlackConnectionState:
    """Current Slack connection state for the active user."""

    has_token: bool
    oauth_client_id: str | None
    default_team_id: str | None
    default_team_name: str | None
    granted_scopes: list[str]
    default_channels: list[str]


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
                        yield Text("")

                        yield BoldText("Required Capabilities", classes="slack-section-title")
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
        return bool(self.config.secrets.get(self._get_project_token_key()))

    def _get_project_name(self) -> str:
        project_name = self.config.get_project_name()
        if not project_name:
            raise ValueError("Slack configuration requires an active Titan project.")
        return project_name

    def _get_project_token_key(self) -> str:
        return build_project_slack_token_key(self._get_project_name())

    def _get_connection_state(self) -> SlackConnectionState:
        plugin_config = self._load_plugin_config()
        return SlackConnectionState(
            has_token=self._has_user_token(),
            oauth_client_id=plugin_config.get("oauth_client_id"),
            default_team_id=plugin_config.get("default_team_id"),
            default_team_name=plugin_config.get("default_team_name"),
            granted_scopes=plugin_config.get("granted_scopes", []),
            default_channels=plugin_config.get("default_channels", []),
        )

    def _save_project_slack_config(self, updates: dict[str, object | None]) -> None:
        project_cfg_path = self.config.project_config_path
        if not project_cfg_path:
            raise ValueError("Slack configuration requires a project config path.")

        config_data = {}
        if project_cfg_path.exists():
            with open(project_cfg_path, "rb") as f:
                config_data = tomli.load(f)

        config_data.setdefault("config_version", getattr(self.config.config, "config_version", "1.0"))
        project_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        plugins = config_data.setdefault("plugins", {})
        plugin_table = plugins.setdefault("slack", {})
        plugin_table["enabled"] = True
        plugin_config = plugin_table.setdefault("config", {})

        for key, value in updates.items():
            if value is None:
                plugin_config.pop(key, None)
            else:
                plugin_config[key] = value

        with open(project_cfg_path, "wb") as f:
            tomli_w.dump(config_data, f)

        self.config.load()

    def _disable_plugin_for_current_project(self) -> None:
        """Remove Slack from the current project's config so it is no longer enabled."""
        project_cfg_path = self.config.project_config_path
        if not project_cfg_path:
            return

        project_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        project_data = {}
        if project_cfg_path.exists():
            with open(project_cfg_path, "rb") as f:
                project_data = tomli.load(f)

        plugins = project_data.get("plugins", {})
        if "slack" in plugins:
            del plugins["slack"]
        if not plugins and "plugins" in project_data:
            del project_data["plugins"]

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
        except NoMatches:
            return

        status_label = "Connected" if state.has_token else "Not connected"
        scopes = ", ".join(state.granted_scopes) if state.granted_scopes else "Not recorded"

        intro.update(
            "Slack stores a personal user token for this project in your keyring.\n"
            "The Slack App, workspace binding, scopes, and default channels are configured per repository."
        )
        status_block.update(
            f"  Status: {status_label}\n"
            f"  OAuth Client ID: {state.oauth_client_id or 'Not set'}\n"
            f"  OAuth Redirect Port: {DEFAULT_OAUTH_REDIRECT_PORT}\n"
            f"  Team ID: {state.default_team_id or 'Not set'}\n"
            f"  Team Name: {state.default_team_name or 'Not set'}\n"
            f"  Granted Scopes: {scopes}\n"
            f"  Default Channels: {', '.join('#' + channel for channel in state.default_channels) if state.default_channels else 'Not set'}"
        )
        oauth_help.update(
            "Titan will open Slack in your browser and complete the OAuth PKCE flow.\n"
            "Create your project's Slack App, enable PKCE, and configure this exact redirect URL in Slack OAuth settings:\n"
            f"  {self._build_redirect_uri()}\n"
            "The redirect URL in Slack must match exactly, including host, port, and path.\n"
            "For example, `127.0.0.1` and `localhost` are different values for Slack."
        )
        scopes_block.update(
            "Slack needs scopes that cover:\n"
            "  - user and channel discovery\n"
            "  - conversation history for summaries\n"
            "  - posting messages to direct messages and channels\n\n"
            "After you connect, Titan records the granted scopes above in Current Status."
        )
        connect_help.update("Use Connect Slack to open the browser-based Slack OAuth flow for this repository.")

        client_id_input.value = state.oauth_client_id or ""

        self.query_one("#validate-button", Button).disabled = not state.has_token
        self.query_one("#disconnect-button", Button).disabled = not state.has_token

    @staticmethod
    def _build_redirect_uri() -> str:
        """Build the localhost redirect URI shown to the user."""
        return f"http://127.0.0.1:{DEFAULT_OAUTH_REDIRECT_PORT}/slack/callback"

    def _read_oauth_form_values(self) -> str:
        """Read and validate the OAuth app form values from the screen."""
        client_id = self.query_one("#oauth-client-id-input", Input).value.strip()

        if not client_id:
            raise ValueError("Slack OAuth client ID is required.")

        return client_id

    def _save_oauth_app_config(self, client_id: str) -> None:
        """Persist OAuth app settings for Slack."""
        self._save_project_slack_config(
            {
                "oauth_client_id": client_id,
            }
        )

    def _perform_oauth_connect(self, client_id: str) -> SlackOAuthResult:
        """Run the synchronous Slack OAuth backend flow."""
        flow = SlackOAuthFlow(
            client_id=client_id,
            redirect_port=DEFAULT_OAUTH_REDIRECT_PORT,
        )
        return flow.run()

    def _start_oauth_flow(self) -> None:
        """Start the Slack OAuth flow in a background worker."""
        try:
            client_id = self._read_oauth_form_values()
            self._save_oauth_app_config(client_id)
        except Exception as exc:
            logger.exception("slack_oauth_setup_failed")
            self.app.notify(f"Slack OAuth setup failed: {exc}", severity="error")
            return

        self.app.notify("Opening browser for Slack authorization...", severity="information")
        self.run_worker(
            self._run_oauth_connect(client_id),
            exclusive=True,
        )

    async def _run_oauth_connect(self, client_id: str) -> None:
        """Run the Slack OAuth flow without blocking the UI thread."""
        try:
            result = await asyncio.to_thread(
                self._perform_oauth_connect,
                client_id,
            )
            self.config.secrets.set(
                self._get_project_token_key(), result.access_token, scope="user"
            )
            self._save_project_slack_config(
                {
                    "oauth_client_id": client_id,
                    "default_team_id": result.team_id,
                    "default_team_name": result.team_name,
                    "granted_scopes": result.granted_scopes,
                    "default_channels": self._load_plugin_config().get("default_channels", []),
                }
            )
            self.app.notify("Slack connected successfully.", severity="information")
            self.dismiss(result=True)
        except Exception as exc:
            logger.exception("slack_oauth_run_failed")
            self.app.notify(f"Slack OAuth failed: {exc}", severity="error")

    def _validate_connection(self) -> None:
        plugin_config = self._load_plugin_config()
        client = SlackClient(
            user_token=self.config.secrets.get(self._get_project_token_key()) or "",
            team_id=plugin_config.get("default_team_id"),
        )
        result = client.auth_test()

        match result:
            case ClientSuccess(data=auth):
                self._save_project_slack_config(
                    {
                        "default_team_id": auth.team_id,
                        "default_team_name": auth.team,
                        "granted_scopes": plugin_config.get("granted_scopes", []),
                        "default_channels": plugin_config.get("default_channels", []),
                    }
                )
                self.app.notify(
                    "Slack connection validated successfully.", severity="information"
                )
                self.dismiss(result=True)
            case ClientError(error_message=err):
                raise RuntimeError(err)

    def _disconnect(self) -> None:
        self.config.secrets.delete(self._get_project_token_key(), scope="user")
        self._disable_plugin_for_current_project()
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
