"""
Titan Plugin: App Store Connect

A professional plugin for interacting with Apple's App Store Connect API.
Provides workflows for managing apps and versions.
"""

__version__ = "1.0.0"
__plugin_name__ = "appstore"

from .plugin import AppStorePlugin
from .exceptions import AppStoreConnectError
from .clients.appstore_client import AppStoreConnectClient
from .credentials import CredentialsManager

__all__ = [
    "AppStorePlugin",
    "AppStoreConnectError",
    "AppStoreConnectClient",
    "CredentialsManager",
]
