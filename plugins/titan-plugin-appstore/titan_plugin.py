"""
Titan Plugin Entry Point for App Store Connect.

This module provides the entry point functions that Titan CLI uses
to discover and interact with the AppStore plugin.
"""

from titan_plugin_appstore.plugin import AppStorePlugin

# Create plugin instance
_plugin = AppStorePlugin()


def get_plugin_info():
    """Return plugin metadata for Titan CLI discovery."""
    return _plugin.get_plugin_info()


def get_steps():
    """Return available steps for this plugin."""
    return _plugin.get_steps()


def get_workflows_dir():
    """Return path to workflows directory."""
    return _plugin.get_workflows_dir()


def create_client(config: dict):
    """Build ctx.appstore from plugin config."""
    return _plugin.create_client(config)


__all__ = [
    "AppStorePlugin",
    "get_plugin_info",
    "get_steps",
    "get_workflows_dir",
    "create_client",
]
