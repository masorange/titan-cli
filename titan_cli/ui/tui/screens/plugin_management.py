"""
Plugin Management Screen

Screen for managing installed plugins:
- Enable/disable plugins
- Configure plugin settings
- View plugin status
"""

from textual.app import ComposeResult
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option
from textual.containers import Container, Horizontal, VerticalScroll
from textual.binding import Binding

from titan_cli.ui.tui.icons import Icons
from titan_cli.ui.tui.widgets import (
    Button,
    Text,
    DimText,
    BoldText,
    BoldPrimaryText,
)
from .base import BaseScreen
from .plugin_config_wizard import PluginConfigWizardScreen
from .install_plugin_screen import InstallPluginScreen
from titan_cli.core.plugins.community import (
    get_community_plugin_names,
    get_community_plugin_by_titan_name,
    remove_community_plugin,
    uninstall_community_plugin,
    install_community_plugin,
    save_community_plugin,
    CommunityPluginRecord,
    check_for_update,
    get_github_token,
)
from datetime import datetime, timezone
from titan_cli.core.logging import get_logger
import asyncio
import tomli
import tomli_w

logger = get_logger(__name__)



class PluginManagementScreen(BaseScreen):
    """
    Plugin management screen for enabling/disabling and configuring plugins.

    Displays all installed plugins with their current status and allows:
    - Toggle enable/disable state
    - Configure plugin settings via wizard
    - View plugin information
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("q", "go_back", "Back"),
        Binding("e", "toggle_plugin", "Enable/Disable"),
        Binding("c", "configure_plugin", "Configure"),
        Binding("i", "install_plugin", "Install"),
        Binding("u", "uninstall_plugin", "Uninstall"),
        Binding("U", "update_plugin", "Update"),
    ]

    CSS = """
    PluginManagementScreen {
        align: center middle;
    }

    #plugin-container {
        width: 100%;
        height: 1fr;
        background: $surface-lighten-1;
    }

    #plugin-container Horizontal {
        width: 100%;
        height: 1fr;
        padding: 1;
    }

    #left-panel {
        width: 20%;
        height: 100%;
        border: round $primary;
        border-title-align: center;
        background: $surface-lighten-1;
        padding: 0;
    }

    #left-panel OptionList {
        height: 1fr;
        width: 100%;
        padding: 1;
    }

    #install-plugin-button {
        width: 100%;
        margin: 0;
    }

    #left-panel OptionList > .option-list--option {
        padding: 1;
    }

    #right-panel {
        width: 80%;
        height: 1fr;
        border: round $primary;
        border-title-align: center;
        background: $surface-lighten-1;
        padding: 0;
    }

    #plugin-details {
        height: 100%;
        width: 100%;
        padding: 1;
    }

    #details-content {
        height: auto;
        width: 100%;
    }

    #details-content Text {
        height: 1;
    }

    #details-content > * {
        margin: 0;
    }

    #details-content Horizontal {
        height: auto;
        width: 100%;
        layout: horizontal;
    }

    #details-content Horizontal > * {
        height: auto;
    }

    .button-container {
        height: auto;
        min-height: 5;
        width: 100%;
        padding: 1 1 2 1;
        margin-top: 1;
        background: $surface-lighten-1;
        align: right middle;
    }

    .button-container Button {
        margin-left: 1;
    }
    """

    def __init__(self, config):
        super().__init__(
            config,
            title=f"{Icons.PLUGIN} Plugin Management",
            show_back=True
        )
        self.selected_plugin = None
        self.installed_plugins = []

    def compose_content(self) -> ComposeResult:
        """Compose the plugin management screen."""
        with Container(id="plugin-container"):
            with Horizontal():
                # Left panel: Plugin list + install button
                left_panel = Container(id="left-panel")
                left_panel.border_title = "Installed Plugins"
                with left_panel:
                    yield OptionList(id="plugin-list")
                    yield Button(f"{Icons.PLUGIN} Install Plugin", variant="primary", id="install-plugin-button")

                # Right panel: Plugin details and actions
                right_panel = Container(id="right-panel")
                right_panel.border_title = "Plugin Details"
                with right_panel:
                    with VerticalScroll(id="plugin-details"):
                        yield Container(id="details-content")


    def on_mount(self) -> None:
        """Initialize the screen with plugin list."""
        self._load_plugins()

    def _load_plugins(self) -> None:
        """Load and display installed plugins."""
        self.installed_plugins = self.config.registry.list_installed()

        plugin_list = self.query_one("#plugin-list", OptionList)
        plugin_list.clear_options()

        if not self.installed_plugins:
            plugin_list.add_option(Option("No plugins installed", id="none", disabled=True))
            self._show_no_plugin_selected()
            return

        # Add plugin options
        community_names = get_community_plugin_names()
        for plugin_name in self.installed_plugins:
            is_enabled = self.config.is_plugin_enabled(plugin_name)
            status_icon = Icons.SUCCESS if is_enabled else Icons.ERROR
            status_text = "Enabled" if is_enabled else "Disabled"
            community_badge = " [community]" if plugin_name in community_names else ""

            plugin_list.add_option(
                Option(
                    f"{status_icon} {plugin_name}{community_badge} - {status_text}",
                    id=plugin_name
                )
            )

        # Select first plugin by default
        if self.installed_plugins:
            plugin_list.highlighted = 0
            self.selected_plugin = self.installed_plugins[0]
            self._show_plugin_details(self.selected_plugin)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle plugin selection (Enter key)."""
        if event.option.id == "none":
            return

        self.selected_plugin = event.option.id
        self._show_plugin_details(self.selected_plugin)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Handle plugin highlight change (arrow keys navigation)."""
        if event.option.id == "none":
            return

        self.selected_plugin = event.option.id
        self._show_plugin_details(self.selected_plugin)

    def _show_no_plugin_selected(self) -> None:
        """Display message when no plugin is selected."""
        details = self.query_one("#details-content", Container)
        details.remove_children()

        details.mount(DimText("No plugins installed."))
        details.mount(DimText("Plugins are automatically discovered from installed packages."))

    def _show_plugin_details(self, plugin_name: str) -> None:
        """Display details for the selected plugin."""
        if not plugin_name or plugin_name == "none":
            self._show_no_plugin_selected()
            return
        
        # Get plugin info
        is_enabled = self.config.is_plugin_enabled(plugin_name)
        plugin = self.config.registry._plugins.get(plugin_name)

        # Clear and rebuild details
        details = self.query_one("#details-content", Container)
        details.remove_children()

        # Plugin name
        details.mount(BoldPrimaryText(plugin_name))
        details.mount(Text(""))

        # Status
        if is_enabled:
            details.mount(Static("[bold]Status:[/bold] [green]Enabled[/green]"))
        else:
            details.mount(Static("[bold]Status:[/bold] [red]Disabled[/red]"))

        # Plugin metadata
        if plugin:
            if hasattr(plugin, '__doc__') and plugin.__doc__:
                details.mount(Text(""))  # Spacer
                details.mount(BoldText("Description:"))
                # Clean docstring: remove indentation from each line
                lines = plugin.__doc__.strip().split('\n')
                clean_lines = [line.strip() for line in lines if line.strip()]
                clean_desc = '\n'.join(clean_lines)
                details.mount(DimText(clean_desc))
                details.mount(Text(""))

            version = self.config.registry.get_plugin_version(plugin_name)
            details.mount(Static(f"[bold]Version:[/bold] {version}"))

        # Check if plugin has configuration schema
        has_config = False
        if plugin and hasattr(plugin, 'get_config_schema'):
            try:
                schema = plugin.get_config_schema()
                if schema and schema.get('properties'):
                    has_config = True
            except Exception:
                pass

        details.mount(Text(""))  # Spacer
        if has_config:
            details.mount(DimText("✓ This plugin supports configuration"))
        else:
            details.mount(DimText("✗ This plugin has no configuration options"))

        # Show current configuration if enabled
        if is_enabled and self.config.config and self.config.config.plugins:
            plugin_cfg = self.config.config.plugins.get(plugin_name)
            if plugin_cfg and plugin_cfg.config:
                details.mount(Text(""))  # Spacer
                details.mount(BoldText("Current Configuration:"))
                for key, value in plugin_cfg.config.items():
                    # Don't show secrets
                    if any(secret in key.lower() for secret in ['token', 'password', 'secret', 'api_key']):
                        details.mount(DimText(f"  {key}: ••••••••"))
                    else:
                        details.mount(DimText(f"  {key}: {value}"))

        # Actions
        # Community plugin info
        community_record = get_community_plugin_by_titan_name(plugin_name)
        if community_record:
            details.mount(Text(""))
            details.mount(BoldText("Source:"))
            details.mount(DimText("  Community plugin"))
            details.mount(DimText(f"  {community_record.repo_url}@{community_record.version}"))

        details.mount(Text(""))  # Spacer
        details.mount(BoldText("Actions:"))
        action_verb = "disable" if is_enabled else "enable"
        details.mount(DimText(f"  Press e to {action_verb} this plugin"))
        details.mount(DimText("  Press c to configure this plugin"))
        if community_record:
            details.mount(DimText("  Press u to uninstall this plugin"))

        # Buttons
        details.mount(Text(""))  # Spacer
        buttons = [
            Button("Enable/Disable", variant="default", id="toggle-button"),
            Button("Configure", variant="primary", id="configure-button"),
        ]
        if community_record:
            buttons.append(Button("Update", variant="warning", id="update-button"))
            buttons.append(Button("Uninstall", variant="error", id="uninstall-button"))
        details.mount(Horizontal(*buttons, classes="button-container"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "toggle-button":
            self.action_toggle_plugin()
        elif event.button.id == "configure-button":
            self.action_configure_plugin()
        elif event.button.id == "install-plugin-button":
            self.action_install_plugin()
        elif event.button.id == "update-button":
            self.action_update_plugin()
        elif event.button.id == "uninstall-button":
            self.action_uninstall_plugin()

    def action_toggle_plugin(self) -> None:
        """Toggle enable/disable state of selected plugin."""
        if not self.selected_plugin:
            self.app.notify("Please select a plugin", severity="warning")
            return

        try:
           
            project_cfg_path = self.config.project_config_path
            if not project_cfg_path or not project_cfg_path.exists():
                self.app.notify("No project configuration found", severity="error")
                return

            # Load current config
            with open(project_cfg_path, "rb") as f:
                project_cfg_dict = tomli.load(f)

            # Ensure plugin entry exists
            plugins_table = project_cfg_dict.setdefault("plugins", {})
            plugin_table = plugins_table.setdefault(self.selected_plugin, {})

            # Toggle enabled state
            current_state = plugin_table.get("enabled", True)
            new_state = not current_state
            plugin_table["enabled"] = new_state

            # Save config
            with open(project_cfg_path, "wb") as f:
                tomli_w.dump(project_cfg_dict, f)

            # Reload config
            self.config.load()

            # Refresh display
            self._load_plugins()

            action = "enabled" if new_state else "disabled"
            logger.info("plugin_toggled", plugin=self.selected_plugin, enabled=new_state)
            self.app.notify(f"Plugin '{self.selected_plugin}' {action}", severity="information")

        except Exception as e:
            logger.exception("plugin_toggle_failed", plugin=self.selected_plugin)
            self.app.notify(f"Failed to toggle plugin: {e}", severity="error")

    def action_configure_plugin(self) -> None:
        """Open configuration wizard for selected plugin."""
        if not self.selected_plugin:
            self.app.notify("Please select a plugin", severity="warning")
            return

        # Check if plugin has config schema
        plugin = self.config.registry._plugins.get(self.selected_plugin)
        if not plugin or not hasattr(plugin, 'get_config_schema'):
            self.app.notify("This plugin has no configuration options", severity="warning")
            return

        # Open configuration wizard
        logger.info("plugin_configure_opened", plugin=self.selected_plugin)

        def on_wizard_close(result):
            if result:
                logger.info("plugin_configure_saved", plugin=self.selected_plugin)
                self.config.load()
                self._load_plugins()
            else:
                logger.info("plugin_configure_cancelled", plugin=self.selected_plugin)

        wizard = PluginConfigWizardScreen(self.config, self.selected_plugin)
        self.app.push_screen(wizard, on_wizard_close)

    def action_install_plugin(self) -> None:
        """Open the community plugin install wizard."""
        def on_install_done(result):
            if result:
                self._load_plugins()
                self.app.notify("Plugin installed and loaded!", severity="information")

        self.app.push_screen(InstallPluginScreen(self.config), on_install_done)

    def action_update_plugin(self) -> None:
        """Check for and apply an update to the selected community plugin."""
        if not self.selected_plugin:
            self.app.notify("Please select a plugin", severity="warning")
            return

        record = get_community_plugin_by_titan_name(self.selected_plugin)
        if not record:
            self.app.notify("Only community plugins can be updated", severity="warning")
            return

        self.run_worker(self._run_update(record), exclusive=True)

    async def _run_update(self, record: CommunityPluginRecord) -> None:
        """Check for the latest version and install it if available."""
        self.app.notify(f"Checking for updates to '{record.titan_plugin_name}'…", severity="information", timeout=30)

        token = await asyncio.to_thread(get_github_token)
        latest = await asyncio.to_thread(check_for_update, record, token)

        if not latest:
            self.app.notify(
                f"'{record.titan_plugin_name}' is already up to date ({record.version}).",
                severity="information",
            )
            return

        self.app.notify(
            f"Updating '{record.titan_plugin_name}' {record.version} → {latest}…",
            severity="information",
            timeout=60,
        )

        result = await asyncio.to_thread(
            install_community_plugin, record.repo_url, latest, token
        )

        if result.returncode != 0:
            logger.error("plugin_update_failed", plugin=record.titan_plugin_name, stderr=result.stderr)
            self.app.notify(
                f"Failed to update '{record.titan_plugin_name}': {result.stderr or result.stdout}",
                severity="error",
            )
            return

        # Update tracking record with new version
        remove_community_plugin(record.package_name)
        updated_record = CommunityPluginRecord(
            repo_url=record.repo_url,
            version=latest,
            package_name=record.package_name,
            titan_plugin_name=record.titan_plugin_name,
            installed_at=datetime.now(timezone.utc).isoformat(),
        )
        save_community_plugin(updated_record)

        self.config.load()
        self._load_plugins()
        logger.info("plugin_updated", plugin=record.titan_plugin_name, version=latest)
        self.app.notify(
            f"'{record.titan_plugin_name}' updated to {latest}.",
            severity="information",
        )

    def action_uninstall_plugin(self) -> None:
        """Uninstall the selected community plugin."""
        if not self.selected_plugin:
            self.app.notify("Please select a plugin", severity="warning")
            return

        record = get_community_plugin_by_titan_name(self.selected_plugin)
        if not record:
            self.app.notify("Only community plugins can be uninstalled", severity="warning")
            return

        self.run_worker(self._run_uninstall(record.package_name), exclusive=True)

    async def _run_uninstall(self, package_name: str) -> None:
        """Run pipx/pip uninstall and update tracking file."""
        logger.info("plugin_uninstall_started", package=package_name)
        self.app.notify(f"Uninstalling '{package_name}'…", severity="information", timeout=30)
        result = await asyncio.to_thread(uninstall_community_plugin, package_name)

        if result.returncode != 0:
            logger.error("plugin_uninstall_failed", package=package_name, stderr=result.stderr or result.stdout)
            self.app.notify(
                f"Failed to uninstall '{package_name}': {result.stderr or result.stdout}",
                severity="error",
            )
            return

        logger.info("plugin_uninstalled", package=package_name)
        remove_community_plugin(package_name)
        self.config.load()
        self._load_plugins()
        self.app.notify(f"Plugin '{package_name}' uninstalled.", severity="information")
