"""
Titan TUI Module

Textual-based Terminal User Interface for Titan CLI.
"""
from .app import TitanApp

__all__ = ["TitanApp"]


def launch_tui():
    """
    Launch the Titan TUI application.

    This is the main entry point for running Titan in TUI mode.
    """
    from titan_cli.core.config import TitanConfig
    from titan_cli.core.plugins.plugin_registry import PluginRegistry

    # Initialize config with plugin registry
    plugin_registry = PluginRegistry()
    config = TitanConfig(registry=plugin_registry)

    # Create and run the app
    app = TitanApp(config=config)
    app.run()
