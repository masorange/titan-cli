"""
TAP (Titan Adapter Protocol) - Main API

Simplified imports for TAP architecture components.

Example:
    from titan.tap import TAPManager, TAPProtocol
    
    # Create TAP manager
    tap = TAPManager.from_config("config/tap.yml")
    
    # Get adapter
    adapter = tap.get("anthropic")
"""

# Import core TAP components with TAP-prefixed aliases
from titan_cli.adapters.protocol import ToolAdapter as TAPProtocol
from titan_cli.adapters.registry import AdapterRegistry as TAPRegistry
from titan_cli.adapters.loader import AdapterLoader as TAPLoader
from titan_cli.adapters.factory import AdapterFactory as TAPFactory
from titan_cli.adapters.manager import AdapterManager as TAPManager

# Import verification utilities
from titan_cli.adapters.protocol import (
    verify_adapter as verify_tap_adapter,
    is_valid_adapter as is_valid_tap_adapter,
    get_adapter_info as get_tap_adapter_info
)

# Keep original names for backward compatibility
from titan_cli.adapters.protocol import ToolAdapter
from titan_cli.adapters.registry import AdapterRegistry
from titan_cli.adapters.loader import AdapterLoader
from titan_cli.adapters.factory import AdapterFactory
from titan_cli.adapters.manager import AdapterManager

__all__ = [
    # TAP-prefixed (recommended)
    "TAPProtocol",
    "TAPRegistry",
    "TAPLoader",
    "TAPFactory",
    "TAPManager",
    "verify_tap_adapter",
    "is_valid_tap_adapter",
    "get_tap_adapter_info",
    
    # Original names (backward compatibility)
    "ToolAdapter",
    "AdapterRegistry",
    "AdapterLoader",
    "AdapterFactory",
    "AdapterManager",
]

__version__ = "1.0.0"
__protocol__ = "TAP"
