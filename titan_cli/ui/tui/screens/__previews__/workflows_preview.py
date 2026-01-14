"""
Workflows Screen Preview

Preview application for the WorkflowsScreen component.
Allows testing the workflows UI in isolation with mocked configuration.
"""
from textual.app import App

from titan_cli.core.config import TitanConfig
from titan_cli.core.plugins.plugin_registry import PluginRegistry
from titan_cli.ui.tui.screens.workflows import WorkflowsScreen
from titan_cli.ui.tui.theme import TITAN_THEME_CSS


class WorkflowsPreviewApp(App):
    """
    Preview application for WorkflowsScreen.

    Shows the workflows screen in isolation with a mocked TitanConfig.
    """

    CSS = TITAN_THEME_CSS

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "Workflows Screen Preview"
        self.sub_title = "Testing WorkflowsScreen"

    def on_mount(self) -> None:
        """Initialize and show the workflows screen."""
        # Create a mocked config with plugin registry
        plugin_registry = PluginRegistry()
        config = TitanConfig(registry=plugin_registry)

        # Push the workflows screen
        self.push_screen(WorkflowsScreen(config))


if __name__ == "__main__":
    WorkflowsPreviewApp().run()
