"""
Adapters for different AI frameworks.

All adapters implement the ToolAdapter protocol, providing a consistent
interface for converting TitanTools to framework-specific formats.

This module provides a complete plugin architecture with:
- Protocol-based interfaces (ToolAdapter)
- Centralized registry (AdapterRegistry)
- Configuration-based loading (AdapterLoader)
- Factory pattern with DI (AdapterFactory)
- Complete lifecycle management (AdapterManager)

Quick Start:
    # Simple usage with manager
    from titan.adapters import AdapterManager
    
    manager = AdapterManager.from_config("config/adapters.yml")
    adapter = manager.get("anthropic")
    
    # Direct usage (legacy)
    from titan.adapters import AnthropicAdapter
    
    tools = AnthropicAdapter.convert_tools(titan_tools)
"""

# Protocol
from titan_cli.adapters.protocol import ToolAdapter, verify_adapter

# Concrete adapters
from titan_cli.adapters.anthropic import AnthropicAdapter
from titan_cli.adapters.openai import OpenAIAdapter
from titan_cli.adapters.langraph import LangGraphAdapter

# Plugin architecture components
from titan_cli.adapters.registry import AdapterRegistry, get_registry
from titan_cli.adapters.loader import AdapterLoader, ConfigurationError
from titan_cli.adapters.factory import AdapterFactory
from titan_cli.adapters.manager import AdapterManager

__all__ = [
    # Protocol
    "ToolAdapter",
    "verify_adapter",
    
    # Concrete adapters
    "AnthropicAdapter",
    "OpenAIAdapter",
    "LangGraphAdapter",
    
    # Plugin architecture
    "AdapterRegistry",
    "get_registry",
    "AdapterLoader",
    "ConfigurationError",
    "AdapterFactory",
    "AdapterManager",
]
