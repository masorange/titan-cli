"""TAP (Titan Adapter Protocol) - Framework-agnostic adapter system."""

from titan_cli.tap.protocol import TAPAdapter, verify_adapter, is_valid_adapter
from titan_cli.tap.registry import TAPRegistry
from titan_cli.tap.loader import TAPLoader
from titan_cli.tap.factory import TAPFactory
from titan_cli.tap.manager import TAPManager

__all__ = [
    "TAPAdapter",
    "verify_adapter",
    "is_valid_adapter",
    "TAPRegistry",
    "TAPLoader",
    "TAPFactory",
    "TAPManager",
]
