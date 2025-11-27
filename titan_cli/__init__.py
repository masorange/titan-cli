
# TitanAgents Integration - Core tool system
from titan_cli.core.tool import TitanTool, titanTool, StepType
from titan_cli.core.plugin import PluginManager, PluginMetadata

# TitanAgents Integration - Adapter system
from titan_cli.adapters.manager import AdapterManager

# TitanAgents Integration - TAP (simplified API)
from titan_cli.tap import TAPManager

__all__ = [
    # Existing exports...
    # New exports from TitanAgents
    "TitanTool",
    "titanTool",
    "StepType",
    "PluginManager",
    "PluginMetadata",
    "AdapterManager",
    "TAPManager",
]
