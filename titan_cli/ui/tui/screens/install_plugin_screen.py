"""
Install Plugin Screen

Multi-step wizard for installing community plugins from git repositories.

Steps:
  1. URL     — user enters repo URL with @version
  2. Preview — fetch pyproject.toml metadata + security warning
  3. Install — async pipx inject with progress indicator
  4. Done    — success or error summary
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Input, LoadingIndicator, Static

from titan_cli.core.plugins.community import (
    CommunityPluginRecord,
    build_raw_pyproject_url,
    detect_host,
    fetch_pyproject_toml,
    get_github_token,
    install_community_plugin,
    parse_plugin_metadata,
    parse_repo_url,
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
    PromptInput,
    StepIndicator,
    StepStatus,
    SuccessText,
    Text,
    WizardStep,
)
from .base import BaseScreen


_STEPS = [
    WizardStep(id="url",     title="Repository URL"),
    WizardStep(id="preview", title="Preview"),
    WizardStep(id="install", title="Install"),
    WizardStep(id="done",    title="Done"),
]


class InstallPluginScreen(BaseScreen):
    """
    Wizard for installing a community plugin from a git repository.

    Walks the user through URL entry, plugin preview with security warning,
    async pipx injection, and a final success/error summary.
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
        self._raw_url = ""
        self._base_url = ""
        self._version = ""
        self._token: Optional[str] = None
        self._metadata: dict = {}
        self._install_success = False
        self._installed_record: Optional[CommunityPluginRecord] = None

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
            case "url":
                self._render_url(title, body)
            case "preview":
                self._render_preview(title, body)
            case "install":
                self._render_install(title, body)
            case "done":
                self._render_done(title, body)

    # -----------------------------------------------------------------------
    # Step 1: URL input
    # -----------------------------------------------------------------------

    def _render_url(self, title: Static, body: Container) -> None:
        title.update("Repository URL")
        self._set_next_label("Next")
        self._set_cancel_visible(True)

        body.mount(DimText(
            "Enter the URL of the plugin's git repository.\n"
            "You must include a version tag or commit SHA after @"
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
        # Read current input value even if the user clicked Next without pressing Enter
        try:
            self._raw_url = self.query_one("#prompt-input", Input).value
        except Exception:
            pass

        body = self.query_one("#content-body", Container)
        for w in body.query(ErrorText):
            w.remove()
        try:
            validate_url(self._raw_url)
            self._base_url, self._version = parse_repo_url(self._raw_url)
            return True
        except ValueError as e:
            body.mount(ErrorText(f"{Icons.ERROR} {e}"))
            return False

    # -----------------------------------------------------------------------
    # Step 2: Preview
    # -----------------------------------------------------------------------

    def _render_preview(self, title: Static, body: Container) -> None:
        title.update("Plugin Preview")
        self._set_next_label("Next", disabled=True)
        self._set_cancel_visible(True)

        body.mount(LoadingIndicator())
        body.mount(DimText("Fetching plugin metadata…"))

        self.call_after_refresh(self._start_fetch)

    def _start_fetch(self) -> None:
        self.run_worker(self._fetch_metadata(), exclusive=True)

    async def _fetch_metadata(self) -> None:
        body = self.query_one("#content-body", Container)

        self._token = await asyncio.to_thread(get_github_token)

        host    = detect_host(self._base_url)
        raw_url = build_raw_pyproject_url(self._base_url, self._version, host)

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
            self._set_next_label("Proceed anyway", disabled=True)
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

        self._render_security_warning(body)
        self._set_next_label("I understand, Install")

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
    # Step 3: Install
    # -----------------------------------------------------------------------

    def _render_install(self, title: Static, body: Container) -> None:
        title.update("Installing…")
        self._set_next_label("Next", disabled=True)
        self._set_cancel_visible(False)

        body.mount(LoadingIndicator())
        body.mount(DimText(f"Running pipx inject for {self._base_url}@{self._version}…"))

        self.call_after_refresh(self._start_install)

    def _start_install(self) -> None:
        self.run_worker(self._run_install(), exclusive=True)

    async def _run_install(self) -> None:
        body = self.query_one("#content-body", Container)

        result = await asyncio.to_thread(
            install_community_plugin, self._base_url, self._version, self._token
        )

        body.remove_children()

        if result.returncode != 0:
            self._install_success = False
            pipx_output = result.stderr or result.stdout or "Unknown error"
            body.mount(Panel(
                "pipx inject failed.\n\n"
                "Possible reasons:\n"
                "  • The repository does not exist or is private\n"
                "  • The version tag or commit SHA is incorrect\n"
                "  • pipx is not installed or titan-cli is not injected correctly",
                panel_type="error",
            ))
            body.mount(Text(""))
            body.mount(BoldText("pipx output:"))
            body.mount(DimText(pipx_output[:800]))
        else:
            self._install_success = True

            eps          = self._metadata.get("titan_entry_points", {})
            plugin_name  = next(iter(eps), "")
            package_name = self._metadata.get("name") or self._base_url.rstrip("/").split("/")[-1]

            self._installed_record = CommunityPluginRecord(
                repo_url=self._base_url,
                version=self._version,
                package_name=package_name,
                titan_plugin_name=plugin_name,
                installed_at=datetime.now(timezone.utc).isoformat(),
            )
            save_community_plugin(self._installed_record)

            # Auto-reload: config.load() resets the registry and re-initializes all plugins
            await asyncio.to_thread(self.config.load)

            body.mount(SuccessText(f"{Icons.SUCCESS} Plugin installed successfully!"))

        self._set_next_label("Next")

    # -----------------------------------------------------------------------
    # Step 4: Done
    # -----------------------------------------------------------------------

    def _render_done(self, title: Static, body: Container) -> None:
        self._set_next_label("Finish")
        self._set_cancel_visible(False)

        if self._install_success and self._installed_record:
            title.update("Installation complete")
            r = self._installed_record

            body.mount(SuccessText(f"{Icons.SUCCESS} Plugin ready to use!"))
            body.mount(Text(""))
            if r.package_name:
                body.mount(DimText(f"  Package:     {r.package_name}"))
            if r.version:
                body.mount(DimText(f"  Version:     {r.version}"))
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

        if step_id == "url" and not self._validate_url_step():
            return

        self._load_step(self.current_step + 1)

    def action_cancel(self) -> None:
        self.dismiss(result=False)
