# core/config.py
from pathlib import Path
from typing import Optional, List
import tomli
from .models import TitanConfigModel
from .plugins.plugin_registry import PluginRegistry
from .workflows import WorkflowRegistry, ProjectStepSource, UserStepSource
from .secrets import SecretManager
from .errors import ConfigParseError, ConfigWriteError

class TitanConfig:
    """Manages Titan configuration with global + project merge"""

    GLOBAL_CONFIG = Path.home() / ".titan" / "config.toml"

    def __init__(
        self,
        registry: Optional[PluginRegistry] = None,
        global_config_path: Optional[Path] = None,
        skip_plugin_init: bool = False
    ):
        # Core dependencies
        self.registry = registry or PluginRegistry()

        # These are initialized in load() after config is read
        self.secrets = None  # Set by load()
        self._project_root = None  # Set by load()
        self._active_project_path = None  # Set by load()
        self._workflow_registry = None  # Set by load()
        self._plugin_warnings = []

        # Use custom global config path if provided (for testing), otherwise use default
        self._global_config_path = global_config_path or self.GLOBAL_CONFIG

        # Initial load
        self.load(skip_plugin_init=skip_plugin_init)

    def load(self, skip_plugin_init: bool = False):
        """
        Reloads the entire configuration from disk, including global config
        and the project config from the current working directory.

        Args:
            skip_plugin_init: If True, skip plugin initialization. Useful during setup wizards.
        """
        # Load global config
        self.global_config = self._load_toml(self._global_config_path)

        # Set project root to current working directory
        self._project_root = Path.cwd()
        self._active_project_path = Path.cwd()

        # Look for project config in current directory
        self.project_config_path = self._find_project_config(Path.cwd())

        # Load project config if it exists
        self.project_config = self._load_toml(self.project_config_path)

        # Merge and validate final config
        merged = self._merge_configs(self.global_config, self.project_config)
        self.config = TitanConfigModel(**merged)

        # Re-initialize dependencies that depend on the final config
        # Use current working directory for secrets
        secrets_path = Path.cwd()
        self.secrets = SecretManager(project_path=secrets_path if secrets_path.is_dir() else None)

        # Reset and re-initialize plugins (unless skipped during setup)
        if not skip_plugin_init:
            self.registry.reset()
            self.registry.initialize_plugins(config=self, secrets=self.secrets)
            self._plugin_warnings = self.registry.list_failed()

        # Re-initialize WorkflowRegistry
        # Use current working directory for workflows
        workflow_path = Path.cwd()
        project_step_source = ProjectStepSource(project_root=workflow_path)
        user_step_source = UserStepSource()
        self._workflow_registry = WorkflowRegistry(
            project_root=workflow_path,
            plugin_registry=self.registry,
            project_step_source=project_step_source,
            user_step_source=user_step_source,
            config=self
        )


    def _find_project_config(self, start_path: Optional[Path] = None) -> Optional[Path]:
        """Search for .titan/config.toml up the directory tree"""
        current = (start_path or Path.cwd()).resolve()

        # In a test environment, Path.cwd() might not be under /home/
        # and we need a stopping condition.
        sentinel = Path(current.root)
        
        while current != current.parent and current != sentinel:
            config_path = current / ".titan" / "config.toml"
            if config_path.exists():
                return config_path
            current = current.parent

        return None

    def _load_toml(self, path: Optional[Path]) -> dict:
        """Load TOML file, returning an empty dict on failure."""
        if not path or not path.exists():
            return {}

        with open(path, "rb") as f:
            try:
                return tomli.load(f)
            except tomli.TOMLDecodeError as e:
                # Wrap the generic exception. Warnings will be handled by CLI commands.
                _ = ConfigParseError(file_path=str(path), original_exception=e)
                return {}

    def _merge_configs(self, global_cfg: dict, project_cfg: dict) -> dict:
        """Merge global and project configs (project overrides global)"""
        merged = {**global_cfg}

        # Project config overrides global
        for key, value in project_cfg.items():
            if key == "plugins" and isinstance(value, dict):
                merged_plugins = merged.setdefault("plugins", {})

                for plugin_name, plugin_data_project in value.items():
                    plugin_data_global = merged_plugins.get(plugin_name, {})

                    # Start with a copy of the global plugin config for this specific plugin
                    # This ensures all global settings (like 'enabled') are carried over
                    # unless explicitly overridden.
                    final_plugin_data = {**plugin_data_global}

                    # Merge top-level keys from project config, excluding 'config'
                    for pk, pv in plugin_data_project.items():
                        if pk != "config":
                            final_plugin_data[pk] = pv

                    # Handle the nested 'config' dictionary separately (deep merge)
                    config_section_global = plugin_data_global.get("config", {})
                    config_section_project = plugin_data_project.get("config", {})

                    if config_section_global or config_section_project:
                        final_plugin_data["config"] = {**config_section_global, **config_section_project}
                    elif "config" in final_plugin_data: # If global had a config, and project didn't touch it
                         pass # Keep the global config

                    merged_plugins[plugin_name] = final_plugin_data
            elif key == "ai" and isinstance(value, dict):
                # AI config should be merged intelligently (global + project)
                # Global AI config is always available, project can override specific settings
                merged_ai = merged.setdefault("ai", {})

                # Merge providers (project providers supplement global providers)
                if "providers" in value:
                    merged_providers = merged_ai.setdefault("providers", {})
                    # Deep merge: preserve global fields, override with project fields
                    for provider_id, provider_data in value["providers"].items():
                        if provider_id in merged_providers:
                            # Provider exists in global: deep merge (extend, not replace)
                            merged_providers[provider_id] = {**merged_providers[provider_id], **provider_data}
                        else:
                            # New provider: just add it
                            merged_providers[provider_id] = provider_data

                # Project can override default provider, otherwise keep global
                if "default" in value:
                    merged_ai["default"] = value["default"]

                # Merge any other AI settings
                for ai_key, ai_value in value.items():
                    if ai_key not in ("providers", "default"):
                        merged_ai[ai_key] = ai_value
            else:
                merged[key] = value

        return merged

    @property
    def project_root(self) -> Path:
        """Return the resolved project root path."""
        return self._project_root

    @property
    def active_project_path(self) -> Optional[Path]:
        """Return the path to the currently active project."""
        return self._active_project_path

    @property
    def workflows(self) -> WorkflowRegistry:
        """Access to workflow registry."""
        return self._workflow_registry


    def get_enabled_plugins(self) -> List[str]:
        """Get list of enabled plugins"""
        if not self.config or not self.config.plugins:
            return []
        return [
            name for name, plugin_cfg in self.config.plugins.items()
            if plugin_cfg.enabled
        ]

    def get_plugin_warnings(self) -> List[str]:
        """Get list of failed or misconfigured plugins."""
        return self._plugin_warnings

    def get_project_name(self) -> Optional[str]:
        """Get the current project name from project config."""
        if self.config and self.config.project:
            return self.config.project.name
        return None

    def _save_global_config(self):
        """Saves the current state of the global config to disk."""
        if not self._global_config_path.parent.exists():
            try:
                self._global_config_path.parent.mkdir(parents=True)
            except OSError as e:
                raise ConfigWriteError(file_path=str(self._global_config_path), original_exception=e)

        existing_global_config = {}
        if self._global_config_path.exists():
            try:
                with open(self._global_config_path, "rb") as f:
                    import tomllib
                    existing_global_config = tomllib.load(f)
            except Exception:
                pass

        # Save only AI configuration to global config
        # Project-specific settings are stored in project's .titan/config.toml
        config_to_save = self.config.model_dump(exclude_none=True)

        if 'ai' in config_to_save:
            existing_global_config['ai'] = config_to_save['ai']

        try:
            with open(self._global_config_path, "wb") as f:
                import tomli_w
                tomli_w.dump(existing_global_config, f)
        except ImportError as e:
            raise ConfigWriteError(file_path=str(self._global_config_path), original_exception=e)
        except Exception as e:
            raise ConfigWriteError(file_path=str(self._global_config_path), original_exception=e)

    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """Check if plugin is enabled"""
        if not self.config or not self.config.plugins:
            return False
        plugin_cfg = self.config.plugins.get(plugin_name)
        return plugin_cfg.enabled if plugin_cfg else False

    def get_status_bar_info(self) -> dict:
        """
        Get information for the status bar display.

        Returns:
            A dict with keys: 'ai_info', 'project_name'
            Values are strings or None if not available.
        """
        # Extract AI info
        ai_info = None
        if self.config and self.config.ai:
            ai_config = self.config.ai
            default_provider_id = ai_config.default

            if default_provider_id and default_provider_id in ai_config.providers:
                provider_config = ai_config.providers[default_provider_id]
                provider_name = provider_config.provider
                model = provider_config.model or "default"
                ai_info = f"{provider_name}/{model}"

        # Extract project name from project config
        project_name = self.get_project_name()

        return {
            'ai_info': ai_info,
            'project_name': project_name
        }

