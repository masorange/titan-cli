"""
Plugin system for TitanAgents.

This module provides the plugin architecture that allows extending
the system without modifying the core.
"""

from typing import Protocol, List, Dict, Any, Optional, Type
from dataclasses import dataclass
from pathlib import Path
import importlib
import importlib.util
import sys

from titan_cli.core.tool import TitanTool, get_all_tools, StepType


@dataclass
class PluginMetadata:
    """Metadata for a plugin."""
    name: str
    version: str
    author: str
    description: str
    layer: StepType = StepType.SERVICE


class TitanPlugin(Protocol):
    """
    Protocol (interface) for TitanAgents plugins.
    
    All plugins must implement this interface. It's a Protocol (not ABC)
    to allow structural subtyping - any class with these methods is a plugin.
    """
    
    metadata: PluginMetadata
    
    def initialize(self) -> None:
        """Initialize the plugin (setup resources, connections, etc.)."""
        ...
    
    def register_tools(self) -> List[TitanTool]:
        """
        Return all tools provided by this plugin.
        
        Tools are typically created using the @titanTool decorator
        within the plugin class.
        """
        ...
    
    def shutdown(self) -> None:
        """Cleanup resources when the plugin is unloaded."""
        ...


class PluginManager:
    """
    Manages the lifecycle of plugins and their tools.
    
    This class is responsible for:
    - Discovering plugins from directories
    - Loading and initializing plugins
    - Managing the tool registry
    - Providing tools to agents and CLI
    
    Example:
        pm = PluginManager()
        pm.discover_plugins("./plugins")
        pm.register_plugin(MyCustomPlugin())
        
        # Get a specific tool
        tool = pm.get_tool("read_file")
        
        # Get all tools from a layer
        service_tools = pm.get_tools_by_layer(StepType.SERVICE)
    """
    
    def __init__(self):
        self.plugins: Dict[str, TitanPlugin] = {}
        self.tools: Dict[str, TitanTool] = {}
    
    def discover_plugins(self, plugin_dir: str) -> List[str]:
        """
        Automatically discover and load plugins from a directory.
        
        Looks for Python modules in the directory that contain a class
        implementing the TitanPlugin protocol.
        
        Args:
            plugin_dir: Path to the directory containing plugins
        
        Returns:
            List of loaded plugin names
        """
        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            raise ValueError(f"Plugin directory does not exist: {plugin_dir}")
        
        loaded_plugins: List[str] = []
        
        # Iterate through all Python files in the directory
        for plugin_file in plugin_path.rglob("plugin.py"):
            try:
                # Load the module
                module_name = f"plugins.{plugin_file.parent.name}"
                spec = importlib.util.spec_from_file_location(module_name, plugin_file)
                
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    
                    # Look for plugin classes
                    for item_name in dir(module):
                        item = getattr(module, item_name)
                        
                        # Check if it's a class that implements TitanPlugin
                        if (
                            isinstance(item, type)
                            and hasattr(item, "metadata")
                            and hasattr(item, "initialize")
                            and hasattr(item, "register_tools")
                            and hasattr(item, "shutdown")
                            and item_name != "TitanPlugin"
                        ):
                            # Instantiate and register the plugin
                            plugin_instance = item()
                            self.register_plugin(plugin_instance)
                            loaded_plugins.append(plugin_instance.metadata.name)
                            
            except Exception as e:
                print(f"Error loading plugin from {plugin_file}: {e}")
        
        return loaded_plugins
    
    def register_plugin(self, plugin: TitanPlugin) -> None:
        """
        Manually register a plugin instance.
        
        Args:
            plugin: An instance of a class implementing TitanPlugin
        """
        # Initialize the plugin
        plugin.initialize()
        
        # Store the plugin
        self.plugins[plugin.metadata.name] = plugin
        
        # Register all its tools
        for tool in plugin.register_tools():
            self.tools[tool.name] = tool
            print(f"✓ Registered tool: {tool.name} (from plugin: {plugin.metadata.name})")
    
    def unregister_plugin(self, plugin_name: str) -> None:
        """
        Unregister a plugin and remove its tools.
        
        Args:
            plugin_name: Name of the plugin to unregister
        """
        if plugin_name not in self.plugins:
            raise ValueError(f"Plugin not found: {plugin_name}")
        
        plugin = self.plugins[plugin_name]
        
        # Get list of tool names from this plugin
        plugin_tools = plugin.register_tools()
        plugin_tool_names = {tool.name for tool in plugin_tools}
        
        # Remove all tools from this plugin
        tools_to_remove = [
            tool_name
            for tool_name in self.tools.keys()
            if tool_name in plugin_tool_names
        ]
        
        for tool_name in tools_to_remove:
            del self.tools[tool_name]
        
        # Shutdown the plugin
        plugin.shutdown()
        
        # Remove from registry
        del self.plugins[plugin_name]
    
    def get_tool(self, name: str) -> Optional[TitanTool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def get_all_tools(self) -> List[TitanTool]:
        """Get all registered tools."""
        return list(self.tools.values())
    
    def get_tools_by_layer(self, layer: StepType) -> List[TitanTool]:
        """
        Get all tools from a specific architectural layer.
        
        Args:
            layer: The layer (LIBRARY, SERVICE, or STEP)
        
        Returns:
            List of tools in that layer
        """
        return [tool for tool in self.tools.values() if tool.step_type == layer]
    
    def get_tools_requiring_ai(self) -> List[TitanTool]:
        """Get all tools that require AI assistance."""
        return [tool for tool in self.tools.values() if tool.requires_ai]
    
    def get_plugin(self, name: str) -> Optional[TitanPlugin]:
        """Get a plugin by name."""
        return self.plugins.get(name)
    
    def list_plugins(self) -> List[str]:
        """List all registered plugin names."""
        return list(self.plugins.keys())
    
    def get_plugin_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get metadata information about a plugin."""
        plugin = self.get_plugin(name)
        if not plugin:
            return None
        
        return {
            "name": plugin.metadata.name,
            "version": plugin.metadata.version,
            "author": plugin.metadata.author,
            "description": plugin.metadata.description,
            "layer": plugin.metadata.layer.value,
            "tools": [tool.name for tool in plugin.register_tools()],
        }
