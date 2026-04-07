"""
Install Plugin Screen

Multi-step wizard for installing community plugins.

Step 0: Channel — choose between Stable (git) or Dev Local (path)
Stable branch:
  1. URL     — user enters repo URL with @version
  2. Preview — fetch pyproject.toml + resolve tag → commit SHA
  3. Install — pipx inject git+url@<resolved_sha>
  4. Done    — success or error summary

Dev Local branch:
  1. Path    — user enters absolute path to local repo
  2. Preview — read local pyproject.toml (no network)
  3. Activate — save source override in project config
  4. Done    — success or error summary
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import tomli
import tomli_w

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Input, LoadingIndicator, Static

from titan_cli.core.logging import get_logger
from titan_cli.core.plugins.community import (
    CommunityPluginRecord,
    PluginChannel,
    build_raw_pyproject_url,
    detect_host,
    fetch_pyproject_toml,
    get_github_token,
    install_community_plugin,
    parse_plugin_metadata,
    parse_repo_url,
    remove_community_plugin_by_name,
    resolve_ref_to_commit_sha,
    save_community_plugin,
    validate_url,
)
from titan_cli.ui.tui.icons import Icons
from titan_cli.ui.tui.widgets import (
    BoldText,
    Button,
    DimText,
    ErrorText,
    Panel,
    PromptChoice,
    PromptInput,
    StepIndicator,
    StepStatus,
    SuccessText,
    Text,
    WizardStep,
)
from titan_cli.ui.tui.widgets.prompt_choice import ChoiceOption

from .base import BaseScreen

logger = get_logger(__name__)


_STEPS = [
    WizardStep(id="channel", title="Channel"),
    WizardStep(id="source",  title="Source"),
    WizardStep(id="preview", title="Preview"),
    WizardStep(id="install", title="Install"),
    WizardStep(id="done",    title="Done"),
]


class InstallPluginScreen(BaseScreen):
    """
    Wizard for installing a community plugin.

    Step 0 lets the user choose between stable (git URL pinned to SHA) and
    dev_local (editable install from a local path). The remaining four steps
    share the same layout but render different content depending on the channel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    InstallPluginScreen {
        align: center middle;
    }

    #wizard-container {
        width: 100%;
        height: 1fr;
        background: $surface-lighten-1;
        padding: 0 2 1 2;
    }

    #steps-panel {
        width: 20%;
        height: 100%;
        border: round $primary;
        border-title-align: center;
        background: $surface-lighten-1;
        padding: 0;
    }

    #steps-content {
        padding: 1;
    }

    StepIndicator {
        height: auto;
        margin-bottom: 1;
    }

    #content-panel {
        width: 80%;
        height: 100%;
        border: round $primary;
        border-title-align: center;
        background: $surface-lighten-1;
        padding: 0;
        layout: vertical;
    }

    #content-scroll {
        height: 1fr;
    }

    #content-area {
        padding: 1;
        height: auto;
    }

    #content-title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
        height: auto;
    }

    #content-body {
        height: auto;
        margin-bottom: 2;
    }

    #button-container {
        height: auto;
        padding: 1 2;
        background: $surface-lighten-1;
        border-top: solid $primary;
        align: right middle;
    }

    #button-container Button {
        margin-left: 1;
    }

    LoadingIndicator {
        height: 3;
        margin: 1 0;
    }
    """

    def __init__(self, config):
        super().__init__(
            config,
            title=f"{Icons.PLUGIN} Install Community Plugin",
            show_back=False,
            show_status_bar=False,
        )
        self.current_step = 0
        self._channel: str = PluginChannel.STABLE

        # Stable-only state
        self._raw_url: str = ""
        self._base_url: str = ""
        self._requested_ref: str = ""
        self._resolved_commit: Optional[str] = None
        self._token: Optional[str] = None

        # Dev local-only state
        self._local_path: str = ""

        # Shared state
        self._metadata: dict = {}
        self._install_success = False
        self._installed_record: Optional[CommunityPluginRecord] = None
        self._plugin_has_config = False

    # -----------------------------------------------------------------------
    # Composition
    # -----------------------------------------------------------------------

    def compose_content(self) -> ComposeResult:
        with Container(id="wizard-container"):
            with Horizontal():
                left_panel = VerticalScroll(id="steps-panel")
                left_panel.border_title = "Steps"
                with left_panel:
                    with Container(id="steps-content"):
                        for i, step in enumerate(_STEPS, 1):
                            status = StepStatus.IN_PROGRESS if i == 1 else StepStatus.PENDING
                            yield StepIndicator(i, step, status=status)

                right_panel = Container(id="content-panel")
                right_panel.border_title = "Install Plugin"
                with right_panel:
                    with VerticalScroll(id="content-scroll"):
                        with Container(id="content-area"):
                            yield Static("", id="content-title")
                            yield Container(id="content-body")

                    with Horizontal(id="button-container"):
                        yield Button("Cancel", variant="default", id="cancel-button")
                        yield Button("Next", variant="primary", id="next-button")

    def on_mount(self) -> None:
        self._load_step(0)

    # -----------------------------------------------------------------------
    # Step indicators
    # -----------------------------------------------------------------------

    def _update_indicators(self, active: int) -> None:
        for i, indicator in enumerate(self.query(StepIndicator)):
            if i < active:
                indicator.status = StepStatus.COMPLETED
            elif i == active:
                indicator.status = StepStatus.IN_PROGRESS
            else:
                indicator.status = StepStatus.PENDING
            indicator.refresh()

    # -----------------------------------------------------------------------
    # Navigation helpers
    # -----------------------------------------------------------------------

    def _set_next_label(self, label: str, disabled: bool = False) -> None:
        btn = self.query_one("#next-button", Button)
        btn.label = label
        btn.disabled = disabled

    def _set_cancel_visible(self, visible: bool) -> None:
        self.query_one("#cancel-button", Button).display = visible

    def _set_next_visible(self, visible: bool) -> None:
        self.query_one("#next-button", Button).display = visible

    # -----------------------------------------------------------------------
    # Step dispatcher
    # -----------------------------------------------------------------------

    def _load_step(self, index: int) -> None:
        self.current_step = index
        self._update_indicators(index)

        title = self.query_one("#content-title", Static)
        body  = self.query_one("#content-body", Container)
        body.remove_children()

        match _STEPS[index].id:
            case "channel":
                self._render_channel(title, body)
            case "source":
                if self._channel == PluginChannel.DEV_LOCAL:
                    self._render_path(title, body)
                else:
                    self._render_url(title, body)
            case "preview":
                if self._channel == PluginChannel.DEV_LOCAL:
                    self._render_preview_dev_local(title, body)
                else:
                    self._render_preview_stable(title, body)
            case "install":
                self._render_install(title, body)
            case "done":
                self._render_done(title, body)

    # -----------------------------------------------------------------------
    # Step 0: Channel selection
    # -----------------------------------------------------------------------

    def _render_channel(self, title: Static, body: Container) -> None:
        title.update("Installation Channel")
        self._set_next_visible(False)
        self._set_cancel_visible(True)

        body.mount(DimText("Choose how to install the community plugin."))
        body.mount(Text(""))

        def on_select(value: str) -> None:
            self._channel = value
            self._set_next_visible(True)
            self._load_step(1)

        body.mount(PromptChoice(
            question="",
            options=[
                ChoiceOption(
                    value=PluginChannel.STABLE,
                    label=f"{Icons.PLUGIN} Stable (from git)",
                    variant="primary",
                ),
                ChoiceOption(
                    value=PluginChannel.DEV_LOCAL,
                    label=f"{Icons.PLUGIN} Dev Local (from path)",
                    variant="default",
                ),
            ],
            on_select=on_select,
            on_cancel=self.action_cancel,
        ))

        body.mount(Text(""))
        body.mount(BoldText("Stable"))
        body.mount(DimText(
            "  Installs from a git repository pinned to a specific version tag.\n"
            "  The tag is resolved to a commit SHA at install time — immutable."
        ))
        body.mount(Text(""))
        body.mount(BoldText("Dev Local"))
        body.mount(DimText(
            "  Uses a local repository directly from your project config.\n"
            "  Titan loads the plugin from that path for this project.\n"
            "  Intended for plugin contributors."
        ))

    # -----------------------------------------------------------------------
    # Step 1 (Stable): URL input
    # -----------------------------------------------------------------------

    def _render_url(self, title: Static, body: Container) -> None:
        title.update("Repository URL")
        self._set_next_label("Next")
        self._set_next_visible(True)
        self._set_cancel_visible(True)

        body.mount(DimText(
            "Enter the URL of the plugin's git repository.\n"
            "Include a version tag or commit SHA after @"
        ))
        body.mount(Text(""))
        body.mount(DimText("  Example: https://github.com/user/titan-plugin-example@v1.0.0"))
        body.mount(Text(""))

        def on_submit(value: str):
            self._raw_url = value
            self.query_one("#next-button", Button).action_press()

        body.mount(PromptInput(
            question="Repository URL",
            default=self._raw_url,
            placeholder="https://github.com/user/titan-plugin@v1.0.0",
            on_submit=on_submit,
            on_cancel=self.action_cancel,
        ))

    def _validate_url_step(self) -> bool:
        try:
            self._raw_url = self.query_one("#prompt-input", Input).value
        except Exception:
            pass

        body = self.query_one("#content-body", Container)
        for w in body.query(ErrorText):
            w.remove()
        try:
            validate_url(self._raw_url)
            self._base_url, self._requested_ref = parse_repo_url(self._raw_url)
            return True
        except ValueError as e:
            body.mount(ErrorText(f"{Icons.ERROR} {e}"))
            return False

    # -----------------------------------------------------------------------
    # Step 1 (Dev Local): Path input
    # -----------------------------------------------------------------------

    def _render_path(self, title: Static, body: Container) -> None:
        title.update("Local Repository Path")
        self._set_next_label("Next")
        self._set_next_visible(True)
        self._set_cancel_visible(True)

        body.mount(DimText(
            "Enter the absolute path to the local plugin repository.\n"
            "The directory must contain a pyproject.toml with a Titan entry point."
        ))
        body.mount(Text(""))
        body.mount(DimText("  Example: /path/to/my-titan-plugin"))
        body.mount(Text(""))

        def on_submit(value: str):
            self._local_path = value
            self.query_one("#next-button", Button).action_press()

        body.mount(PromptInput(
            question="Local path",
            default=self._local_path,
            placeholder="/path/to/my-titan-plugin",
            on_submit=on_submit,
            on_cancel=self.action_cancel,
        ))

    def _validate_path_step(self) -> bool:
        try:
            self._local_path = self.query_one("#prompt-input", Input).value
        except Exception:
            pass

        body = self.query_one("#content-body", Container)
        for w in body.query(ErrorText):
            w.remove()

        path = self._local_path.strip()
        if not path:
            body.mount(ErrorText(f"{Icons.ERROR} Path cannot be empty."))
            return False

        p = Path(path)
        if not p.is_dir():
            body.mount(ErrorText(f"{Icons.ERROR} Directory does not exist: {path}"))
            return False

        if not (p / "pyproject.toml").is_file():
            body.mount(ErrorText(f"{Icons.ERROR} No pyproject.toml found in {path}"))
            return False

        self._local_path = str(p.resolve())
        return True

    # -----------------------------------------------------------------------
    # Step 2 (Stable): Preview — fetch metadata + resolve SHA
    # -----------------------------------------------------------------------

    def _render_preview_stable(self, title: Static, body: Container) -> None:
        title.update("Plugin Preview")
        self._set_next_label("Next", disabled=True)
        self._set_cancel_visible(True)

        body.mount(LoadingIndicator())
        body.mount(DimText("Fetching plugin metadata and resolving commit SHA…"))

        self.call_after_refresh(self._start_fetch_stable)

    def _start_fetch_stable(self) -> None:
        self.run_worker(self._fetch_metadata_stable(), exclusive=True)

    async def _fetch_metadata_stable(self) -> None:
        body = self.query_one("#content-body", Container)

        self._token = await asyncio.to_thread(get_github_token)
        host = detect_host(self._base_url)

        # Resolve tag/ref → commit SHA (security anchor: installs always use the SHA)
        resolved_sha, sha_error = await asyncio.to_thread(
            resolve_ref_to_commit_sha, self._base_url, self._requested_ref, host, self._token
        )

        if sha_error:
            body.remove_children()
            body.mount(Panel(
                f"Could not resolve '{self._requested_ref}' to a commit SHA.\n\n{sha_error}",
                panel_type="error",
            ))
            self._set_next_label("Next", disabled=True)
            return

        self._resolved_commit = resolved_sha

        raw_url = build_raw_pyproject_url(self._base_url, self._resolved_commit, host)

        if raw_url is None:
            body.remove_children()
            body.mount(Panel(
                "Unknown host — cannot preview plugin metadata.\n"
                "Proceed with extra caution.",
                panel_type="warning",
            ))
            self._render_security_warning(body)
            self._set_next_label("I understand, Install")
            return

        content, error = await asyncio.to_thread(fetch_pyproject_toml, raw_url, self._token)

        body.remove_children()

        if error == "not_found":
            body.mount(Panel(
                "Repository or version not found.\n"
                "Check that the URL and version tag are correct.",
                panel_type="error",
            ))
            self._set_next_label("Next", disabled=True)
            return

        if error == "network_error":
            body.mount(Panel(
                "Could not reach the repository.\n"
                "Check your internet connection and try again.",
                panel_type="error",
            ))
            self._render_security_warning(body)
            self._set_next_label("Proceed anyway")
            return

        self._metadata = parse_plugin_metadata(content)

        if self._metadata.get("parse_error"):
            body.mount(Panel(
                "Could not read plugin metadata — pyproject.toml may be malformed.",
                panel_type="warning",
            ))
        else:
            self._render_metadata(body)
            if not self._metadata.get("titan_entry_points"):
                body.mount(Panel(
                    "This package does not declare a Titan plugin entry point.\n"
                    "Installing it will have no effect inside Titan.",
                    panel_type="warning",
                ))

        body.mount(Text(""))
        body.mount(BoldText("Version resolution"))
        body.mount(DimText(f"  Requested:       {self._requested_ref}"))
        body.mount(DimText(f"  Installs commit: {self._resolved_commit}"))

        self._render_security_warning(body)
        self._set_next_label("I understand, Install")

    # -----------------------------------------------------------------------
    # Step 2 (Dev Local): Preview — read local pyproject.toml
    # -----------------------------------------------------------------------

    def _render_preview_dev_local(self, title: Static, body: Container) -> None:
        title.update("Plugin Preview")
        self._set_next_label("Next", disabled=True)
        self._set_cancel_visible(True)

        body.mount(LoadingIndicator())
        body.mount(DimText("Reading local plugin metadata…"))

        self.call_after_refresh(self._start_fetch_dev_local)

    def _start_fetch_dev_local(self) -> None:
        self.run_worker(self._fetch_metadata_dev_local(), exclusive=True)

    async def _fetch_metadata_dev_local(self) -> None:
        body = self.query_one("#content-body", Container)

        try:
            pyproject_path = Path(self._local_path) / "pyproject.toml"
            content = await asyncio.to_thread(pyproject_path.read_text, encoding="utf-8")
            self._metadata = parse_plugin_metadata(content)
        except Exception as e:
            body.remove_children()
            body.mount(Panel(
                f"Could not read pyproject.toml: {e}",
                panel_type="error",
            ))
            self._set_next_label("Next", disabled=True)
            return

        body.remove_children()

        if self._metadata.get("parse_error"):
            body.mount(Panel(
                "Could not parse pyproject.toml — it may be malformed.",
                panel_type="warning",
            ))
        else:
            self._render_metadata(body)
            if not self._metadata.get("titan_entry_points"):
                body.mount(Panel(
                    "This package does not declare a Titan plugin entry point.\n"
                    "Installing it will have no effect inside Titan.",
                    panel_type="warning",
                ))

        body.mount(Text(""))
        body.mount(BoldText("Dev local install"))
        body.mount(DimText(f"  Path: {self._local_path}"))
        body.mount(DimText(
            "  Titan will load the plugin directly from this repository path.\n"
            "  No editable install is required."
        ))

        self._render_security_warning(body)
        self._set_next_label("I understand, Install")

    # -----------------------------------------------------------------------
    # Shared metadata rendering
    # -----------------------------------------------------------------------

    def _render_metadata(self, body: Container) -> None:
        m = self._metadata
        body.mount(BoldText("Plugin information"))
        body.mount(Text(""))

        if m.get("name"):
            body.mount(DimText(f"  Package:     {m['name']}"))
        if m.get("version"):
            body.mount(DimText(f"  Version:     {m['version']}"))
        if m.get("description"):
            body.mount(DimText(f"  Description: {m['description']}"))
        if m.get("authors"):
            body.mount(DimText(f"  Authors:     {', '.join(m['authors'])}"))

        eps = m.get("titan_entry_points", {})
        if eps:
            body.mount(Text(""))
            body.mount(BoldText("Titan plugin entry points"))
            for key, value in eps.items():
                body.mount(DimText(f"  {key} = {value}"))

        deps = m.get("python_deps", [])
        if deps:
            body.mount(Text(""))
            body.mount(BoldText("Python dependencies"))
            for dep in deps[:10]:
                body.mount(DimText(f"  • {dep}"))
            if len(deps) > 10:
                body.mount(DimText(f"  … and {len(deps) - 10} more"))

        body.mount(Text(""))

    def _render_security_warning(self, body: Container) -> None:
        body.mount(Panel(
            "SECURITY WARNING\n\n"
            "This is third-party code not reviewed or verified by Titan.\n"
            "Installing it grants full access to your system and credentials.\n"
            "Only install plugins from sources you trust.",
            panel_type="warning",
        ))

    # -----------------------------------------------------------------------
    # Step 3: Install (shared dispatcher by channel)
    # -----------------------------------------------------------------------

    def _render_install(self, title: Static, body: Container) -> None:
        title.update("Installing…")
        self._set_next_label("Next", disabled=True)
        self._set_cancel_visible(False)

        if self._channel == PluginChannel.DEV_LOCAL:
            body.mount(DimText(f"Saving dev local source for {self._local_path}…"))
        else:
            body.mount(DimText(f"Running pipx inject for {self._base_url}@{self._resolved_commit}…"))

        body.mount(LoadingIndicator())
        self.call_after_refresh(self._start_install)

    def _start_install(self) -> None:
        self.run_worker(self._run_install(), exclusive=True)

    async def _run_install(self) -> None:
        body = self.query_one("#content-body", Container)

        if self._channel == PluginChannel.DEV_LOCAL:
            result = None
        else:
            result = await asyncio.to_thread(
                install_community_plugin, self._base_url, self._resolved_commit, self._token
            )

        body.remove_children()

        if result is not None and result.returncode != 0:
            self._install_success = False
            output = result.stderr or result.stdout or "Unknown error"
            logger.error(
                "community_plugin_install_failed",
                channel=self._channel,
                output=output,
            )
            body.mount(Panel(
                "Installation failed.\n\n"
                "Possible reasons:\n"
                "  • The repository or path does not exist\n"
                "  • The commit SHA is unreachable\n"
                "  • pipx or pip is not configured correctly",
                panel_type="error",
            ))
            body.mount(Text(""))
            body.mount(BoldText("Output:"))
            body.mount(DimText(output[:800]))
        else:
            self._install_success = True

            eps          = self._metadata.get("titan_entry_points", {})
            plugin_name  = next(iter(eps), "")
            package_name = (
                self._metadata.get("name")
                or (Path(self._local_path).name if self._channel == PluginChannel.DEV_LOCAL
                    else self._base_url.rstrip("/").split("/")[-1])
            )

            if self._channel == PluginChannel.DEV_LOCAL:
                self._installed_record = CommunityPluginRecord(
                    repo_url="",
                    package_name=package_name,
                    titan_plugin_name=plugin_name,
                    installed_at=datetime.now(timezone.utc).isoformat(),
                    channel=PluginChannel.DEV_LOCAL,
                    dev_local_path=self._local_path,
                    requested_ref=None,
                    resolved_commit=None,
                )
                await asyncio.to_thread(
                    self._save_project_plugin_source,
                    plugin_name,
                    PluginChannel.DEV_LOCAL,
                    self._local_path,
                )
            else:
                self._installed_record = CommunityPluginRecord(
                    repo_url=self._base_url,
                    package_name=package_name,
                    titan_plugin_name=plugin_name,
                    installed_at=datetime.now(timezone.utc).isoformat(),
                    channel=PluginChannel.STABLE,
                    dev_local_path=None,
                    requested_ref=self._requested_ref,
                    resolved_commit=self._resolved_commit,
                )
                remove_community_plugin_by_name(plugin_name)
                save_community_plugin(self._installed_record)
                await asyncio.to_thread(
                    self._save_project_plugin_source,
                    plugin_name,
                    PluginChannel.STABLE,
                    None,
                )
            await asyncio.to_thread(self.config.load)

            installed_plugin = self.config.registry._plugins.get(plugin_name)
            if installed_plugin and hasattr(installed_plugin, "get_config_schema"):
                try:
                    schema = installed_plugin.get_config_schema()
                    self._plugin_has_config = bool(schema.get("properties"))
                except Exception:
                    self._plugin_has_config = False

            body.mount(SuccessText(f"{Icons.SUCCESS} Plugin installed successfully!"))

        if self._plugin_has_config and self._installed_record:
            plugin_name = self._installed_record.titan_plugin_name
            self.call_after_refresh(lambda pn=plugin_name: self._open_config_wizard(pn))
        else:
            self._set_next_label("Next")

    def _open_config_wizard(self, plugin_name: str) -> None:
        from .plugin_config_wizard import PluginConfigWizardScreen
        wizard = PluginConfigWizardScreen(self.config, plugin_name)
        self.app.push_screen(wizard, lambda _: self._load_step(self.current_step + 1))

    def _save_project_plugin_source(
        self,
        plugin_name: str,
        channel: str,
        path: Optional[str],
    ) -> None:
        """Persist the active source for a plugin in the current project config."""
        project_cfg_path = self.config.project_config_path or (self.config.project_root / ".titan" / "config.toml")
        project_cfg_path.parent.mkdir(parents=True, exist_ok=True)

        if project_cfg_path.exists():
            with open(project_cfg_path, "rb") as f:
                project_cfg_dict = tomli.load(f)
        else:
            project_cfg_dict = {}

        plugins_table = project_cfg_dict.setdefault("plugins", {})
        plugin_table = plugins_table.setdefault(plugin_name, {})
        plugin_table["enabled"] = True

        source_table = plugin_table.setdefault("source", {})
        source_table["channel"] = channel
        if channel == PluginChannel.DEV_LOCAL and path:
            source_table["path"] = path
        else:
            source_table.pop("path", None)

        with open(project_cfg_path, "wb") as f:
            tomli_w.dump(project_cfg_dict, f)

    # -----------------------------------------------------------------------
    # Step 4: Done
    # -----------------------------------------------------------------------

    def _render_done(self, title: Static, body: Container) -> None:
        self._set_next_label("Finish")
        self._set_cancel_visible(False)
        self._set_next_visible(True)

        if self._install_success and self._installed_record:
            title.update("Installation complete")
            r = self._installed_record

            body.mount(SuccessText(f"{Icons.SUCCESS} Plugin ready to use!"))
            body.mount(Text(""))

            if r.package_name:
                body.mount(DimText(f"  Package:     {r.package_name}"))
            if r.channel == PluginChannel.STABLE and r.requested_ref:
                body.mount(DimText(f"  Version:     {r.requested_ref}"))
                body.mount(DimText(f"  Commit:      {r.resolved_commit}"))
            elif r.channel == PluginChannel.DEV_LOCAL and r.dev_local_path:
                body.mount(DimText(f"  Path:        {r.dev_local_path}"))
                body.mount(DimText(
                    "  This project now loads the plugin from that local path.\n"
                    "  Switching back to stable only requires changing the source."
                ))
            if r.titan_plugin_name:
                body.mount(DimText(f"  Plugin name: {r.titan_plugin_name}"))
            body.mount(Text(""))

            if r.titan_plugin_name:
                body.mount(Panel(
                    f"The plugin '{r.titan_plugin_name}' is now available.\n"
                    "Enable it in Plugin Management to use it in your workflows.",
                    panel_type="info",
                ))
            else:
                body.mount(Panel(
                    "The package was installed but no Titan plugin entry point was found.\n"
                    "The plugin may not follow the Titan plugin format.",
                    panel_type="warning",
                ))
        else:
            title.update("Installation failed")
            body.mount(Panel(
                "The plugin could not be installed.\n"
                "Check the error details in the previous step.",
                panel_type="error",
            ))

    # -----------------------------------------------------------------------
    # Button handling
    # -----------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next-button":
            self._handle_next()
        elif event.button.id == "cancel-button":
            self.action_cancel()

    def _handle_next(self) -> None:
        step_id = _STEPS[self.current_step].id

        if self.current_step == len(_STEPS) - 1:
            self.dismiss(result=self._install_success)
            return

        if step_id == "source":
            if self._channel == PluginChannel.DEV_LOCAL:
                if not self._validate_path_step():
                    return
            else:
                if not self._validate_url_step():
                    return

        self._load_step(self.current_step + 1)

    def action_cancel(self) -> None:
        self.dismiss(result=False)
