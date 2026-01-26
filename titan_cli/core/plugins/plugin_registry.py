# core/plugin_registry.py
from importlib.metadata import entry_points
from typing import Dict, List, Any, Optional
from ..errors import PluginLoadError, PluginInitializationError
from .plugin_base import TitanPlugin

class PluginRegistry:
    """Discovers and manages installed plugins."""

    def __init__(self, discover_on_init: bool = True):
        self._plugins: Dict[str, TitanPlugin] = {}
        self._failed_plugins: Dict[str, Exception] = {}
        self._discovered_plugin_names: List[str] = []
        if discover_on_init:
            self.discover()

    def discover(self):
        """Discover all installed Titan plugins."""
        import logging
        logger = logging.getLogger('titan_cli.ui.tui.screens.project_setup_wizard')

        discovered = entry_points(group='titan.plugins')
        self._discovered_plugin_names = [ep.name for ep in discovered]
        logger.debug(f"PluginRegistry.discover() - Found {len(self._discovered_plugin_names)} plugins: {self._discovered_plugin_names}")

        for ep in discovered:
            try:
                logger.debug(f"Loading plugin: {ep.name}")
                plugin_class = ep.load()
                if not issubclass(plugin_class, TitanPlugin):
                    raise TypeError("Plugin class must inherit from TitanPlugin")
                self._plugins[ep.name] = plugin_class()
                logger.debug(f"Successfully loaded plugin: {ep.name}")
            except Exception as e:
                logger.error(f"Failed to load plugin {ep.name}: {e}", exc_info=True)
                error = PluginLoadError(plugin_name=ep.name, original_exception=e)
                self._failed_plugins[ep.name] = error

        logger.debug(f"PluginRegistry.discover() - Loaded {len(self._plugins)} plugins successfully")
        logger.debug(f"PluginRegistry.discover() - Failed {len(self._failed_plugins)} plugins: {list(self._failed_plugins.keys())}")

    def initialize_plugins(self, config: Any, secrets: Any) -> None:
        """
        Initializes all discovered plugins in dependency order.

        Args:
            config: TitanConfig instance
            secrets: SecretManager instance
        """
        import logging
        logger = logging.getLogger('titan_cli.ui.tui.screens.project_setup_wizard')

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
                            # Don't delete from _plugins - keep it available for configuration
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
                    logger.debug(f"Initializing plugin: {name}")
                    plugin.initialize(config, secrets)
                    initialized.add(name)
                    logger.debug(f"Successfully initialized plugin: {name}")
                except Exception as e:
                    logger.error(f"Failed to initialize plugin {name}: {e}", exc_info=True)
                    error = PluginInitializationError(plugin_name=name, original_exception=e)
                    self._failed_plugins[name] = error
                    # Don't delete from _plugins - keep it available for configuration

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

    def list_enabled(self, config: Any) -> List[str]:
        """
        List plugins that are enabled in the current project configuration.

        Args:
            config: TitanConfig instance

        Returns:
            List of enabled plugin names
        """
        if not config or not config.config or not config.config.plugins:
            return []

        enabled = []
        for plugin_name, plugin_config in config.config.plugins.items():
            if hasattr(plugin_config, 'enabled') and plugin_config.enabled:
                enabled.append(plugin_name)

        return enabled

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
