"""
Exceptions for plugin system.
"""


class PluginError(Exception):
    """Base exception for plugin-related errors."""
    pass


class PluginDownloadError(PluginError):
    """Error downloading plugin from registry."""
    pass


class PluginInstallError(PluginError):
    """Error installing plugin."""
    pass


class PluginValidationError(PluginError):
    """Error validating plugin metadata or structure."""
    pass
