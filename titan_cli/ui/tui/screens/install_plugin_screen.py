"""Install a community plugin, pinned for one project or for every project."""

import asyncio
from dataclasses import dataclass
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Input, LoadingIndicator, Static

from titan_cli.core.logging import get_logger
from titan_cli.core.plugins.community_sources import (
    build_raw_pyproject_url,
    detect_host,
    fetch_pyproject_toml,
    get_github_token,
    get_titan_incompatibility,
    parse_plugin_metadata,
    parse_repo_url,
    resolve_ref_to_commit_sha,
    validate_url,
)
from titan_cli.core.plugins.models import PluginPin, PluginPinScope
from titan_cli.core.plugins.runtime import PluginRuntimeManager
from titan_cli.ui.tui.icons import Icons
from titan_cli.ui.tui.widgets import (
    BoldText,
    Button,
    DimText,
    ChoiceOption,
    ErrorCard,
    Panel,
    PromptChoice,
    PromptInput,
    StepIndicator,
    StepStatus,
    SuccessText,
    Text,
    WizardStep,
)

from .base import BaseScreen

logger = get_logger(__name__)


@dataclass
class InstalledPluginSummary:
    """Summary shown after a successful community plugin install."""

    repo_url: str
    package_name: str
    titan_plugin_name: str
    requested_ref: str
    resolved_commit: str
    scope: PluginPinScope = PluginPinScope.PROJECT
    # The current project's own pin, when it hides a freshly installed global one.
    shadowed_by: Optional[PluginPin] = None


_STEPS = [
    WizardStep(id="source",  title="Source"),
    WizardStep(id="scope",   title="Scope"),
    WizardStep(id="preview", title="Preview"),
    WizardStep(id="install", title="Install"),
    WizardStep(id="done",    title="Done"),
]


class InstallPluginScreen(BaseScreen):
    """Wizard for pinning a stable community plugin, per project or globally."""

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
            title=f"{Icons.PLUGIN} Add Plugin",
            show_back=False,
            show_dock=False,
        )
        self.current_step = 0
        self._raw_url: str = ""
        self._base_url: str = ""
        self._requested_ref: str = ""
        self._subdirectory: Optional[str] = None
        self._resolved_commit: Optional[str] = None
        self._scope: PluginPinScope = PluginPinScope.PROJECT
        self._token: Optional[str] = None

        # Shared state
        self._metadata: dict = {}
        self._install_success = False
        self._installed_record: Optional[InstalledPluginSummary] = None
        self._plugin_has_config = False
        self._runtime_manager = PluginRuntimeManager()

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
            case "source":
                self._render_url(title, body)
            case "scope":
                self._render_scope(title, body)
            case "preview":
                self._render_preview_stable(title, body)
            case "install":
                self._render_install(title, body)
            case "done":
                self._render_done(title, body)

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
            "Include a version tag or commit SHA after @.\n"
            "If the plugin lives in a folder of the repository, add :folder after the version."
        ))
        body.mount(Text(""))
        body.mount(DimText(
            "  Example: https://github.com/user/titan-plugin-example@v1.0.0\n"
            "  In a folder: https://github.com/user/monorepo@v1.0.0:plugins/titan-plugin-example"
        ))
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
        for w in body.query(ErrorCard):
            w.remove()
        try:
            validate_url(self._raw_url)
            self._base_url, self._requested_ref, self._subdirectory = parse_repo_url(self._raw_url)
            return True
        except ValueError as e:
            body.mount(ErrorCard(e))
            return False

    # -----------------------------------------------------------------------
    # Step 2: Scope — this project or every project
    # -----------------------------------------------------------------------

    def _render_scope(self, title: Static, body: Container) -> None:
        title.update("Scope")
        self._set_next_label("Next")
        self._set_next_visible(True)
        self._set_cancel_visible(True)

        body.mount(DimText(
            "Where should this plugin be available?\n"
            "Your choice is saved with the plugin's pinned version."
        ))
        body.mount(Text(""))
        body.mount(DimText(
            "  This project  - pinned in .titan/config.toml, shared with your team.\n"
            "  All projects  - pinned in ~/.titan/config.toml, only on this machine."
        ))

        def on_select(value: PluginPinScope) -> None:
            self._scope = value
            self.query_one("#next-button", Button).action_press()

        body.mount(PromptChoice(
            question="Install for",
            options=[
                ChoiceOption(value=PluginPinScope.PROJECT, label="This project", variant="primary"),
                ChoiceOption(value=PluginPinScope.GLOBAL, label="All projects", variant="default"),
            ],
            on_select=on_select,
            on_cancel=self.action_cancel,
        ))

    # -----------------------------------------------------------------------
    # Step 3 (Stable): Preview — fetch metadata + resolve SHA
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

        raw_url = build_raw_pyproject_url(
            self._base_url, self._resolved_commit, host, self._subdirectory
        )

        if raw_url is None:
            body.remove_children()
            body.mount(Panel(
                "Could not build the metadata URL for this repository.",
                panel_type="error",
            ))
            self._set_next_label("Next", disabled=True)
            return

        content, error = await asyncio.to_thread(fetch_pyproject_toml, raw_url, self._token)

        body.remove_children()

        if error == "not_found":
            if self._subdirectory:
                message = (
                    f"No pyproject.toml found in '{self._subdirectory}' at {self._requested_ref}.\n"
                    "The folder must hold the plugin's own pyproject.toml. "
                    "If the plugin's pyproject.toml is at the repository root, drop the :folder part."
                )
            else:
                message = (
                    "Repository or version not found.\n"
                    "Check that the URL and version tag are correct."
                )
            body.mount(Panel(message, panel_type="error"))
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

        from titan_cli import __version__ as titan_version
        incompatibility = get_titan_incompatibility(self._metadata, titan_version)
        if incompatibility:
            body.mount(Panel(
                f"This version cannot be installed: it {incompatibility}",
                panel_type="error",
            ))
            self._set_next_label("Next", disabled=True)
            return

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
        if self._subdirectory:
            body.mount(DimText(f"  Folder:          {self._subdirectory}"))
        body.mount(DimText(f"  Installs commit: {self._resolved_commit}"))

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
        reach = (
            "It will run in EVERY repository you open with Titan, not only this one.\n"
            if self._scope is PluginPinScope.GLOBAL
            else ""
        )
        body.mount(Panel(
            "SECURITY WARNING\n\n"
            "This is third-party code not reviewed or verified by Titan.\n"
            f"{reach}"
            "Installing it grants full access to your system and credentials.\n"
            "Only install plugins from sources you trust.",
            panel_type="warning",
        ))

    # -----------------------------------------------------------------------
    # Step 4: Install
    # -----------------------------------------------------------------------

    def _render_install(self, title: Static, body: Container) -> None:
        title.update("Installing…")
        self._set_next_label("Next", disabled=True)
        self._set_cancel_visible(False)

        body.mount(DimText(f"Preparing isolated runtime for {self._base_url}@{self._resolved_commit}…"))

        body.mount(LoadingIndicator())
        self.call_after_refresh(self._start_install)

    def _start_install(self) -> None:
        self.run_worker(self._run_install(), exclusive=True)

    async def _run_install(self) -> None:
        body = self.query_one("#content-body", Container)
        eps = self._metadata.get("titan_entry_points", {})
        plugin_name = next(iter(eps), "")
        package_name = self._metadata.get("name") or self._base_url.rstrip("/").split("/")[-1]
        # Read before saving: once a global pin is written, the project's own pin
        # (if any) is what keeps winning, and the Done step has to say so.
        project_pin = self.config.get_plugin_pin(plugin_name)
        shadowed_by = (
            project_pin
            if self._scope is PluginPinScope.GLOBAL
            and project_pin is not None
            and project_pin.scope is PluginPinScope.PROJECT
            else None
        )
        error = await asyncio.to_thread(self._prepare_plugin_install, plugin_name)

        body.remove_children()

        if error:
            self._install_success = False
            logger.error(
                "community_plugin_install_failed",
                repo_url=self._base_url,
                resolved_commit=self._resolved_commit,
                output=error,
            )
            body.mount(Panel(
                "Installation failed.\n\n"
                "Possible reasons:\n"
                "  • The repository or path does not exist\n"
                "  • The commit SHA is unreachable\n"
                "  • git or virtualenv setup failed",
                panel_type="error",
            ))
            body.mount(Text(""))
            body.mount(BoldText("Output:"))
            body.mount(DimText(error[:800]))
        else:
            self._install_success = True

            self._installed_record = InstalledPluginSummary(
                repo_url=self._base_url,
                package_name=package_name,
                titan_plugin_name=plugin_name,
                requested_ref=self._requested_ref,
                resolved_commit=self._resolved_commit,
                scope=self._scope,
                shadowed_by=shadowed_by,
            )
            await asyncio.to_thread(self.config.load)

            from .plugin_config_resolver import plugin_has_config_ui

            self._plugin_has_config = plugin_has_config_ui(self.config, plugin_name)

            where = "every project" if self._scope is PluginPinScope.GLOBAL else "this project"
            body.mount(SuccessText(f"{Icons.SUCCESS} Plugin added to {where}."))

        if self._plugin_has_config and self._installed_record:
            plugin_name = self._installed_record.titan_plugin_name
            self.call_after_refresh(lambda pn=plugin_name: self._open_config_wizard(pn))
        else:
            self._set_next_label("Next")

    def _open_config_wizard(self, plugin_name: str) -> None:
        from .plugin_config_resolver import resolve_plugin_config_screen

        self.app.push_screen(
            resolve_plugin_config_screen(self.config, plugin_name),
            lambda _: self._load_step(self.current_step + 1),
        )

    def _prepare_plugin_install(self, plugin_name: str) -> Optional[str]:
        """Persist the pin in the chosen scope and provision its isolated runtime."""
        try:
            self.config.set_plugin_pin(
                plugin_name,
                self._scope,
                repo_url=self._base_url,
                requested_ref=self._requested_ref,
                resolved_commit=self._resolved_commit,
                subdirectory=self._subdirectory,
            )
            self._runtime_manager.ensure_stable_runtime(
                plugin_name=plugin_name,
                repo_url=self._base_url,
                resolved_commit=self._resolved_commit,
                token=self._token,
                subdirectory=self._subdirectory,
            )
        except Exception as e:
            return str(e)
        return None

    # -----------------------------------------------------------------------
    # Step 5: Done
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
            if r.requested_ref:
                body.mount(DimText(f"  Version:     {r.requested_ref}"))
                body.mount(DimText(f"  Commit:      {r.resolved_commit}"))
            if r.titan_plugin_name:
                body.mount(DimText(f"  Plugin name: {r.titan_plugin_name}"))
            body.mount(Text(""))

            if r.titan_plugin_name:
                if r.scope is PluginPinScope.GLOBAL:
                    pinned_in = "~/.titan/config.toml, so it is available in every project"
                else:
                    pinned_in = "this project's .titan/config.toml"
                body.mount(Panel(
                    f"The plugin '{r.titan_plugin_name}' is now available.\n"
                    f"Titan pinned this version in {pinned_in} and prepared its local runtime.",
                    panel_type="info",
                ))
                if r.shadowed_by is not None:
                    body.mount(Panel(
                        "This project pins its own version "
                        f"({r.shadowed_by.requested_ref or r.shadowed_by.resolved_commit[:12]}), "
                        "which takes precedence over the one you just installed here.",
                        panel_type="warning",
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
            if not self._validate_url_step():
                return

        self._load_step(self.current_step + 1)

    def action_cancel(self) -> None:
        self.dismiss(result=False)
