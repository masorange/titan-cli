"""
Titan TUI Application

Main Textual application for Titan CLI with a fixed dock and theme support.
"""
from textual.app import App
from textual.binding import Binding

from typing import Any, Callable, Optional, Sequence

from titan_cli.ai.router.session import AISessionOverride
from titan_cli.core.config import TitanConfig
from titan_cli.core.logging import get_logger
from titan_cli.core.mods import AppStart, build_mod_bus
from titan_cli.core.utils import find_project_root
from titan_cli.core.plugins.plugin_registry import PluginRegistry
from titan_cli.external_cli.launcher import launcher_for
from .mods_ui import TitanModHost
from .theme import TITAN_THEME_CSS
from .screens import MainMenuScreen


class TitanApp(App):
    """
    The main Titan TUI application.

    This is a Textual-based TUI that provides a visual interface for Titan CLI,
    with a fixed dock at the bottom and interactive menus/workflows.

    The layout is:
    - Header (top): Title and clock
    - Main content area (scrollable)
    - Dock (bottom, fixed): launcher, mods' slots, project, branch and AI info
    """

    # Combine theme CSS with app-specific CSS
    CSS = TITAN_THEME_CSS

    # Allow text selection in terminal (Shift+Mouse will work in most terminals)
    ENABLE_COMMAND_PALETTE = False  # Disable Ctrl+\ interference

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
        Binding("ctrl+shift+c", "toggle_copy_mode", "Copy Mode"),
        Binding("f2", "quick_cli", "AI CLI"),
        Binding("f3", "quick_model", "AI Model"),
        Binding("f4", "toggle_mods_panel", "Panel"),
        Binding("f6", "toggle_dock", "Dock"),
        Binding("?", "help", "Help"),
    ]

    def __init__(self, config: TitanConfig = None, initial_screen=None, mod_dirs: Sequence[str] = (), **kwargs):
        """
        Initialize the Titan TUI application.

        Args:
            config: TitanConfig instance. If None, creates a new one.
            initial_screen: Initial screen to show. If None, shows MainMenuScreen.
                          Can be a screen instance or a callable that returns a screen.
            mod_dirs: Extra mod folders from `--mod-dir`, one mod each.
        """
        super().__init__(**kwargs)

        # Initialize config and plugin registry
        if config is None:
            plugin_registry = PluginRegistry()
            config = TitanConfig(registry=plugin_registry)

        self.config = config
        self._initial_screen = initial_screen
        # Folding the dock is a session choice, shared by every screen's dock.
        self.dock_collapsed = False
        self.title = "Titan CLI"
        self.sub_title = "Development Tools Orchestrator"

        # What the user chose for this session only, via F2/F3. One mutable instance for
        # the whole app: every workflow run is handed this object, not a copy, so changing
        # it between runs takes effect without rebuilding anything. Never persisted.
        self.ai_session_override = AISessionOverride()

        # Mods load once per app: their hooks wrap every workflow run from here on.
        registry = getattr(config, "registry", None)
        self.mods = build_mod_bus(_plugin_mod_paths(config, registry), mod_dirs)
        self.mods_host = TitanModHost(self, self.mods, registry)
        self.mods.host = self.mods_host

    def on_mount(self) -> None:
        """Initialize app and show initial screen."""
        # Before the first screen composes, so the panes mods open are there for it.
        try:
            self.mods.dispatch("app.start", AppStart(project_root=str(find_project_root())), lambda e: None)
        except Exception:
            get_logger(__name__).exception("mods_app_start_failed")
        if self._initial_screen is not None:
            # Use custom initial screen
            if callable(self._initial_screen):
                screen = self._initial_screen()
            else:
                screen = self._initial_screen
            self.push_screen(screen)
        else:
            # Default: show main menu
            self.push_screen(MainMenuScreen(self.config))

    async def launch_external_cli(self, cli_name: str, prompt: str = None) -> int:
        """
        Launch an external CLI tool (like Claude CLI or Gemini CLI).

        Suspends the TUI, launches the external CLI, then restores the TUI.

        Args:
            cli_name: Name of the CLI to launch (e.g., "claude", "gemini")
            prompt: Optional initial prompt to pass to the CLI

        Returns:
            Exit code from the CLI tool
        """

        # Suspend the TUI temporarily
        with self.suspend():
            launcher = launcher_for(cli_name)
            exit_code = launcher.launch(
                prompt=prompt, model=self.model_for_cli(cli_name)
            )

        # TUI is automatically restored here
        return exit_code

    def model_for_cli(self, cli_name: str) -> Optional[str]:
        """The model this CLI should run with, session override included.

        `config.get_cli_model` sees only the persisted global pin. A session override
        outranks it everywhere else - the resolver honours it and the dock
        advertises it - so reading the config directly here made a session-only model
        show as active while never reaching the CLI that was launched.
        """
        override = self.ai_session_override.model_for(remote=False)
        if override and (
            self.ai_session_override.cli is None
            or self.ai_session_override.cli == cli_name
        ):
            return override
        return self.config.get_cli_model(cli_name)

    def action_quick_cli(self) -> None:
        """Open the quick CLI picker from any screen."""
        from titan_cli.ui.tui.screens.ai_routing import cli_choices, installed_clis
        from titan_cli.ui.tui.screens.model_picker import open_model_picker_for_cli

        ai_config = self.config.config.ai if self.config.config else None
        checker = self._availability_checker()
        installed = installed_clis(
            checker.available_headless_clis(), checker.available_interactive_clis()
        )
        current = ai_config.default_cli if ai_config else None
        models = ai_config.cli_models if ai_config else {}

        def open_picker(instance, current_model, on_picked) -> None:
            open_model_picker_for_cli(
                self, instance, current=current_model, on_picked=on_picked,
                allow_clear=True,
            )

        def apply(result) -> None:
            if result.instance and result.instance != current:
                self.config.set_default_ai_cli(result.instance)
            target = result.instance or current
            if result.clear_model and target:
                self.config.clear_cli_model(target)
            elif result.model and target:
                self.config.set_cli_model(target, result.model)

        self._open_quick_picker(
            question="Which CLI should Titan run?",
            noun="CLI",
            remote=False,
            choices=cli_choices(installed, models),
            current=current,
            current_model=models.get(current) if current else None,
            pinned_tasks_remote=False,
            empty_message="No supported CLI is installed. Install one and reopen this picker.",
            open_picker=open_picker,
            apply=apply,
            use_for_session=lambda result: self._apply_session(result, remote=False),
        )

    def action_quick_model(self) -> None:
        """Open the quick connection picker from any screen.

        The same widget F2 opens, loaded with connections instead of CLIs: they are the
        same question asked of different transports, so a change to one is a change to
        both by construction rather than by remembering.
        """
        from titan_cli.ui.tui.screens.ai_routing import connection_choices
        from titan_cli.ui.tui.screens.model_picker import open_model_picker_for_connection

        ai_config = self.config.config.ai if self.config.config else None
        connections = ai_config.connections if ai_config else {}
        current = ai_config.default_connection if ai_config else None
        current_cfg = connections.get(current) if current else None

        def open_picker(instance, current_model, on_picked) -> None:
            open_model_picker_for_connection(
                self, self.config, instance, current=current_model, on_picked=on_picked
            )

        def apply(result) -> None:
            if result.instance and result.instance != current:
                self.config.set_default_ai_connection(result.instance)
            target = result.instance or current
            # No clear_model branch: a connection REQUIRES a default_model, so the picker
            # does not offer to unpin one (see SelectModelModal.allow_clear).
            if result.model and target:
                self.config.update_ai_connection(target, {"default_model": result.model})

        self._open_quick_picker(
            question="Which connection should answer?",
            noun="connection",
            remote=True,
            choices=connection_choices(connections),
            current=current,
            current_model=getattr(current_cfg, "default_model", None),
            pinned_tasks_remote=True,
            empty_message="No AI connection is configured. Add one in AI Configuration.",
            open_picker=open_picker,
            apply=apply,
            use_for_session=lambda result: self._apply_session(result, remote=True),
        )

    def _open_quick_picker(
        self,
        *,
        question,
        noun,
        remote,
        choices,
        current,
        current_model,
        pinned_tasks_remote,
        empty_message,
        open_picker,
        apply,
        use_for_session,
    ) -> None:
        """Push the shared quick picker and route its one result to the right writer."""
        from titan_cli.ui.tui.screens.ai_routing import QuickInstanceModal, tasks_pinning

        # The whole stack, not just the top: while the model picker this modal pushes
        # is on top, `self.screen` is that picker, so F2/F3 would stack a second
        # composer over it whose callbacks still write into the first one's state.
        if any(isinstance(s, QuickInstanceModal) for s in self.screen_stack):
            return

        def on_picked(result) -> None:
            if result is None or not result.changes_anything:
                return
            if result.clear_session:
                self.clear_ai_session_override(remote=pinned_tasks_remote)
                return
            dropped = None
            try:
                if result.session_only:
                    dropped = use_for_session(result)
                else:
                    apply(result)
            except Exception as e:
                # `apply` can make two writes, so a failure on the second leaves the
                # first persisted: the dock has to be repainted either way, and the
                # wording must not claim the whole change was rejected.
                self.refresh_dock()
                self.notify(
                    f"Only part of that could be applied: {e}", severity="error"
                )
                return
            self.refresh_dock()
            self.notify(self._quick_picker_notice(result, noun, dropped=dropped))

        self.push_screen(
            QuickInstanceModal(
                question,
                choices,
                noun=noun,
                remote=remote,
                current=current,
                current_model=current_model,
                session_override=self.ai_session_override,
                pinned_tasks=tasks_pinning(
                    self._task_preferences(), remote=pinned_tasks_remote
                ),
                open_model_picker=open_picker,
                empty_message=empty_message,
            ),
            callback=on_picked,
        )

    def _apply_session(self, result, *, remote: bool) -> Optional[str]:
        """Hold the composition for this session only, writing nothing.

        Returns a model override the instance change invalidated, so the caller can say
        so rather than letting it vanish.
        """
        override = self.ai_session_override
        dropped = None
        if result.instance:
            if remote:
                dropped = override.use_connection(result.instance)
            else:
                dropped = override.use_cli(result.instance)
        instance = result.instance or (
            override.connection if remote else override.cli
        )
        if result.clear_model:
            if remote:
                override.set_connection_model(instance, None)
            else:
                override.set_cli_model(instance, None)
        elif result.model:
            if remote:
                override.set_connection_model(instance, result.model)
            else:
                override.set_cli_model(instance, result.model)
        return None if result.model else dropped

    @staticmethod
    def _quick_picker_notice(result, noun: str, *, dropped: Optional[str] = None) -> str:
        parts = [p for p in (result.instance, result.model) if p]
        what = " / ".join(parts) if parts else f"the {noun}'s own default"
        notice = (
            f"{what} for this session only - your saved settings are untouched."
            if result.session_only
            else f"Saved: {what}."
        )
        if dropped:
            notice += f" Dropped the {dropped} model override."
        return notice

    def _availability_checker(self):
        from titan_cli.ai.router.availability import AIAvailabilityChecker
        from titan_cli.core.security import create_broker_factory

        ai_config = self.config.config.ai if self.config.config else None
        broker = create_broker_factory(self.config.project_root).for_plugin("core")
        return AIAvailabilityChecker(ai_config, broker)

    def _task_preferences(self):
        """The persisted per-task preferences, or None when AI is unconfigured."""
        ai_config = self.config.config.ai if self.config.config else None
        preferences = ai_config.preferences if ai_config else None
        return preferences.tasks if preferences else None

    def clear_ai_session_override(self, *, remote: Optional[bool] = None) -> None:
        """Drop the session override so saved configuration applies again.

        `remote` scopes it to one transport, which is what a picker asks for: it only
        reported its own half, so clearing the other from there would remove something
        the user could not see.
        """
        override = self.ai_session_override
        if remote is None:
            if not override.is_active:
                return
            override.clear()
        else:
            if not override.is_active_for(remote):
                return
            override.clear_for(remote)
        self.refresh_dock()
        self.notify("Session override cleared - your saved settings apply again.")

    def refresh_dock(self) -> None:
        """Repaint the current screen's dock, if it has one.

        The session override is app state with no config write behind it, so nothing else
        would tell the dock to change - and an override the dock does not show is an
        override the user will forget is on.
        """
        screen = self.screen
        updater = getattr(screen, "refresh_dock", None)
        if callable(updater):
            try:
                updater()
            except Exception:
                # Never fatal - a stale dock must not take the app down - but not silent
                # either: a dock that stops updating is exactly what this method exists
                # to prevent, and a bare pass leaves no trace of it happening.
                get_logger(__name__).debug("dock_refresh_failed", exc_info=True)

    def action_toggle_mods_panel(self) -> None:
        """Collapse or expand the mods' side panel, on every screen."""
        self.mods_host.toggle_collapsed()

    def action_toggle_dock(self) -> None:
        """Fold or unfold the dock's launcher, on every screen."""
        from titan_cli.ui.tui.widgets.dock import Dock

        self.dock_collapsed = not self.dock_collapsed
        for dock in self.screen.query(Dock):
            dock.show_collapsed(self.dock_collapsed)

    def action_help(self) -> None:
        """Show or hide the list of every shortcut active here, Titan's and the mods'."""
        from textual.widgets import HelpPanel

        if self.screen.query(HelpPanel):
            self.action_hide_help_panel()
        else:
            self.action_show_help_panel()

    def action_mod_key(self, key: str) -> None:
        """A key a mod bound with `m.keys.bind`."""
        self.mods_host.press_key(key)

    # -- the dock's launcher: Titan's destinations, from any screen ---------

    def _launcher_refusal(self, screen_type: type) -> Optional[str]:
        from titan_cli.ui.tui.screens.workflow_execution import WorkflowExecutionScreen

        if isinstance(self.screen, screen_type):
            return "already here"
        if any(isinstance(screen, WorkflowExecutionScreen) for screen in self.screen_stack):
            # Leaving would orphan the run; its screen is still under whatever opens.
            return "a workflow is running; finish it first"
        return None

    def _launch(self, screen_type: type, make: Callable[[], Any]) -> None:
        refusal = self._launcher_refusal(screen_type)
        if refusal == "already here":
            return
        if refusal is not None:
            self.notify(refusal, severity="warning")
            return
        self.push_screen(make())

    def action_open_workflows(self) -> None:
        """Open the workflow list."""
        from titan_cli.ui.tui.screens.workflows import WorkflowsScreen

        self._launch(WorkflowsScreen, lambda: WorkflowsScreen(self.config))

    def action_open_plugins(self) -> None:
        """Open plugin management.

        Enabling or disabling a plugin changes which workflows exist, so the home
        screen's cached discovery is marked stale for when it is shown again.
        """
        from titan_cli.ui.tui.screens.main_menu import MainMenuScreen
        from titan_cli.ui.tui.screens.plugin_management import PluginManagementScreen

        if self._launcher_refusal(PluginManagementScreen) is None:
            for screen in self.screen_stack:
                if isinstance(screen, MainMenuScreen):
                    screen.mark_discovery_stale()
        self._launch(PluginManagementScreen, lambda: PluginManagementScreen(self.config))

    def action_open_ai_config(self) -> None:
        """Open AI configuration."""
        from titan_cli.ui.tui.screens.ai_config import AIConfigScreen

        self._launch(AIConfigScreen, lambda: AIConfigScreen(self.config))

    def action_toggle_copy_mode(self) -> None:
        """Toggle copy mode - disables mouse capture to allow text selection."""
        # Toggle mouse capture
        current = getattr(self, '_copy_mode', False)
        self._copy_mode = not current

        if self._driver is None:
            return

        # Disable/enable mouse reporting at the terminal driver level.
        # `self.mouse_capture = ...` used to be set here, but that attribute
        # doesn't exist on Textual's App - it never actually stopped the
        # terminal's SGR mouse-reporting escape codes, so this toggle was a
        # no-op besides the notification.
        if self._copy_mode:
            # Disable mouse - allows terminal selection
            self._driver._disable_mouse_support()
            self.notify("📋 Copy Mode ON - Use mouse to select text, press Ctrl+Shift+C to exit", timeout=3)
        else:
            # Re-enable mouse
            self._driver._enable_mouse_support()
            self.notify("🖱️  Copy Mode OFF - Mouse interactions restored", timeout=3)


def _plugin_mod_paths(config, registry) -> dict:
    """Where each enabled plugin keeps the mods it ships."""
    paths = {}
    try:
        enabled = registry.list_enabled(config) if registry is not None else []
    except Exception:
        return paths
    for name in enabled:
        try:
            plugin = registry.get_plugin(name)
            path = plugin.mods_path if plugin is not None else None
        except Exception:
            continue
        if path is not None:
            paths[name] = path
    return paths
