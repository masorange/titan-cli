# core/plugin_registry.py
import json
import importlib.util
import sys
from importlib.metadata import entry_points
from pathlib import Path
from typing import Dict, List, Any, Optional
from ..errors import PluginLoadError, PluginInitializationError
from .plugin_base import TitanPlugin

class PluginRegistry:
    """Discovers and manages installed plugins."""

    def __init__(self, discover_on_init: bool = True, plugins_dir: Optional[Path] = None):
        """
        Initialize plugin registry.

        Args:
            discover_on_init: Automatically discover plugins on initialization
            plugins_dir: Custom plugins directory (defaults to .titan/plugins in current dir)
        """
        self._plugins: Dict[str, TitanPlugin] = {}
        self._failed_plugins: Dict[str, Exception] = {}
        self._discovered_plugin_names: List[str] = []

        # Use project-level plugin directory by default
        if plugins_dir is not None:
            self.local_plugins_dir = plugins_dir
        else:
            # Default to current working directory's .titan/plugins
            self.local_plugins_dir = Path.cwd() / ".titan" / "plugins"

        if discover_on_init:
            self.discover()

    def discover(self):
        """Discover all installed Titan plugins from entry points and local directory."""
        # Discover from entry points (installed packages)
        self._discover_from_entry_points()

        # Discover from local plugins directory
        self._discover_from_local_plugins()

    def _discover_from_entry_points(self):
        """Discover plugins from Python entry points (installed packages)."""
        discovered = entry_points(group='titan.plugins')
        self._discovered_plugin_names.extend([ep.name for ep in discovered])

        for ep in discovered:
            # Skip if already loaded from local plugins
            if ep.name in self._plugins:
                continue

            try:
                plugin_class = ep.load()
                if not issubclass(plugin_class, TitanPlugin):
                    raise TypeError("Plugin class must inherit from TitanPlugin")
                self._plugins[ep.name] = plugin_class()
            except Exception as e:
                error = PluginLoadError(plugin_name=ep.name, original_exception=e)
                self._failed_plugins[ep.name] = error

    def _discover_from_local_plugins(self):
        """Discover plugins from project-level .titan/plugins directory."""
        if not self.local_plugins_dir.exists():
            return

        for plugin_dir in self.local_plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue

            # Check for plugin.json
            plugin_json = plugin_dir / "plugin.json"
            if not plugin_json.exists():
                continue

            try:
                # Load plugin metadata
                try:
                    with open(plugin_json) as f:
                        metadata = json.load(f)
                except json.JSONDecodeError as e:
                    error = PluginLoadError(
                        plugin_name=plugin_dir.name,
                        original_exception=f"Invalid JSON in plugin.json: {e}"
                    )
                    self._failed_plugins[plugin_dir.name] = error
                    continue
                except OSError as e:
                    error = PluginLoadError(
                        plugin_name=plugin_dir.name,
                        original_exception=f"Cannot read plugin.json: {e}"
                    )
                    self._failed_plugins[plugin_dir.name] = error
                    continue

                plugin_name = metadata.get("name")
                if not plugin_name:
                    continue

                # Skip if already loaded from entry points
                if plugin_name in self._plugins:
                    continue

                # Add to discovered list
                if plugin_name not in self._discovered_plugin_names:
                    self._discovered_plugin_names.append(plugin_name)

                # Load plugin class
                entry_point = metadata.get("entry_point")
                if not entry_point or ":" not in entry_point:
                    raise ValueError(f"Invalid entry_point in {plugin_json}")

                module_path, class_name = entry_point.split(":", 1)

                # Add plugin directory to sys.path temporarily
                plugin_dir_str = str(plugin_dir)
                if plugin_dir_str not in sys.path:
                    sys.path.insert(0, plugin_dir_str)

                try:
                    # Import module
                    module = importlib.import_module(module_path)

                    # Get plugin class
                    plugin_class = getattr(module, class_name)

                    if not issubclass(plugin_class, TitanPlugin):
                        raise TypeError("Plugin class must inherit from TitanPlugin")

                    # Instantiate plugin
                    self._plugins[plugin_name] = plugin_class()

                finally:
                    # Clean up sys.path
                    if plugin_dir_str in sys.path:
                        sys.path.remove(plugin_dir_str)

            except Exception as e:
                error = PluginLoadError(plugin_name=plugin_dir.name, original_exception=e)
                self._failed_plugins[plugin_dir.name] = error

    def initialize_plugins(self, config: Any, secrets: Any) -> None:
        """
        Initializes all discovered plugins in dependency order.
        
        Args:
            config: TitanConfig instance
            secrets: SecretManager instance
        """
        # Create a copy of plugin names to iterate over, as _plugins might change
        plugins_to_initialize = list(self._plugins.keys())
        initialized = set()

        # Simple dependency resolution loop
        while plugins_to_initialize:
            remaining_plugins_count = len(plugins_to_initialize)
            next_pass_plugins = []

            for name in plugins_to_initialize:
                if name in initialized:
                    continue

                plugin = self._plugins[name]
                dependencies_met = True
                
                # Check if all dependencies are initialized or failed
                for dep_name in plugin.dependencies:
                    if dep_name not in initialized:
                        # If a dependency failed to load/initialize, this plugin also implicitly fails
                        if dep_name in self._failed_plugins:
                            # Mark this plugin as failed due to dependency
                            error = PluginInitializationError(
                                plugin_name=name,
                                original_exception=f"Dependency '{dep_name}' failed to load/initialize."
                            )
                            self._failed_plugins[name] = error
                            del self._plugins[name]
                            dependencies_met = False
                            break
                        else:
                            dependencies_met = False
                            break
                
                if not dependencies_met:
                    if name not in self._failed_plugins: # If not already marked failed by dependency
                        next_pass_plugins.append(name)
                    continue

                # Initialize the plugin if dependencies are met
                try:
                    plugin.initialize(config, secrets)
                    initialized.add(name)
                except Exception as e:
                    error = PluginInitializationError(plugin_name=name, original_exception=e)
                    self._failed_plugins[name] = error
                    del self._plugins[name] # Remove from active plugins

            plugins_to_initialize = next_pass_plugins
            if len(plugins_to_initialize) == remaining_plugins_count and remaining_plugins_count > 0:
                # Circular dependency or unresolvable dependency
                for name in plugins_to_initialize:
                    if name not in self._failed_plugins: # Only mark if not already failed by dependency
                        error = PluginInitializationError(
                            plugin_name=name,
                            original_exception="Circular or unresolvable dependency detected."
                        )
                        self._failed_plugins[name] = error
                        if name in self._plugins: # Only delete if it wasn't deleted by a dep error
                            del self._plugins[name]
                break # Exit the loop if no progress is made

    def list_installed(self) -> List[str]:
        """List successfully loaded plugins."""
        return list(self._plugins.keys())

    def list_discovered(self) -> List[str]:
        """List all discovered plugins by name, regardless of load status."""
        return self._discovered_plugin_names

    def list_failed(self) -> Dict[str, Exception]:
        """
        List plugins that failed to load or initialize.
        
        Returns:
            Dict mapping plugin name to error
        """
        return self._failed_plugins.copy()

    def get_plugin(self, name: str) -> Optional[TitanPlugin]:
        """Get plugin instance by name."""
        return self._plugins.get(name)

    def reset(self):
        """Resets the registry, clearing all loaded plugins and re-discovering."""
        self._plugins.clear()
        self._failed_plugins.clear()
        self.discover()
