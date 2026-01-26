"""
Plugin Management Screen

Screen for managing installed plugins:
- Enable/disable plugins
- Configure plugin settings
- View plugin status
"""

from textual.app import ComposeResult
from textual.widgets import OptionList
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
    SuccessText,
    ErrorText,
)
from .base import BaseScreen
from .plugin_config_wizard import PluginConfigWizardScreen
import tomli
import tomli_w



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
        height: 100%;
        width: 100%;
        padding: 1;
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
                # Left panel: Plugin list
                left_panel = Container(id="left-panel")
                left_panel.border_title = "Installed Plugins"
                with left_panel:
                    yield OptionList(id="plugin-list")

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
        for plugin_name in self.installed_plugins:
            is_enabled = self.config.is_plugin_enabled(plugin_name)
            status_icon = Icons.SUCCESS if is_enabled else Icons.ERROR
            status_text = "Enabled" if is_enabled else "Disabled"

            plugin_list.add_option(
                Option(
                    f"{status_icon} {plugin_name} - {status_text}",
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

        # Status
        status_container = Horizontal()
        details.mount(status_container)
        status_container.mount(BoldText("Status: "))
        if is_enabled:
            status_container.mount(SuccessText("Enabled"))
        else:
            status_container.mount(ErrorText("Disabled"))

        # Plugin metadata
        if plugin:
            if hasattr(plugin, '__doc__') and plugin.__doc__:
                details.mount(Text(""))  # Spacer
                details.mount(BoldText("Description:"))
                details.mount(DimText(plugin.__doc__.strip()))

            if hasattr(plugin, 'version'):
                version_container = Horizontal()
                details.mount(version_container)
                version_container.mount(BoldText("Version: "))
                version_container.mount(Text(plugin.version))

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
        details.mount(Text(""))  # Spacer
        details.mount(BoldText("Actions:"))
        action_verb = "disable" if is_enabled else "enable"
        details.mount(DimText(f"  Press e to {action_verb} this plugin"))
        details.mount(DimText("  Press c to configure this plugin"))

        # Buttons
        details.mount(Text(""))  # Spacer
        button_container = Horizontal(
            Button("Enable/Disable", variant="default", id="toggle-button"),
            Button("Configure", variant="primary", id="configure-button"),
            classes="button-container"
        )
        details.mount(button_container)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "toggle-button":
            self.action_toggle_plugin()
        elif event.button.id == "configure-button":
            self.action_configure_plugin()

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
            self.app.notify(f"Plugin '{self.selected_plugin}' {action}", severity="information")

        except Exception as e:
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
        def on_wizard_close(result):
            """Handle wizard completion."""
            if result:
                # Reload config and refresh display
                self.config.load()
                self._load_plugins()

        wizard = PluginConfigWizardScreen(self.config, self.selected_plugin)
        self.app.push_screen(wizard, on_wizard_close)
