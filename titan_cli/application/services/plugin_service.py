"""Plugin-oriented application services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomli
import tomli_w

from titan_cli.application.models.responses import (
    KnownPluginSummary,
    PluginMutationResult,
)
from titan_cli.core.config import TitanConfig
from titan_cli.core.plugins.available import KNOWN_PLUGINS
from titan_cli.core.plugins.community_sources import PluginChannel


class PluginService:
    """Service layer for plugin inspection and orchestration."""

    def __init__(self, config: TitanConfig) -> None:
        self._config = config

    def list_plugins(self) -> list[str]:
        """List installed plugins known to the current registry."""
        return sorted(self._config.registry.list_installed())

    def list_enabled_plugins(self) -> list[str]:
        """List enabled plugins for the active project/config context."""
        return sorted(self._config.get_enabled_plugins())

    def list_available_plugins(self) -> list[KnownPluginSummary]:
        """Return curated plugins available for guided installation."""
        return [
            KnownPluginSummary(
                name=plugin["name"],
                description=plugin["description"],
                package_name=plugin["package_name"],
                dependencies=list(plugin.get("dependencies", [])),
                source=plugin.get("source", "official"),
                repo_url=plugin.get("repo_url"),
                recommended_ref=plugin.get("recommended_ref"),
            )
            for plugin in KNOWN_PLUGINS
        ]

    def get_config_schema(self, plugin_name: str) -> dict[str, Any]:
        """Return a plugin configuration JSON schema."""
        plugin = self._config.registry.get_plugin(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin '{plugin_name}' is not available.")

        if not hasattr(plugin, "get_config_schema"):
            return {"type": "object", "properties": {}}

        schema = plugin.get_config_schema()
        if not isinstance(schema, dict):
            raise ValueError(f"Plugin '{plugin_name}' returned an invalid schema.")
        return schema

    def set_enabled(self, plugin_name: str, enabled: bool) -> PluginMutationResult:
        """Persist the project-level enabled flag for a plugin."""
        project_cfg = self._load_project_config()
        plugin_table = self._plugin_table(project_cfg, plugin_name)
        plugin_table["enabled"] = enabled
        self._write_project_config(project_cfg)
        return PluginMutationResult(
            plugin_name=plugin_name,
            changed=True,
            message=f"Plugin '{plugin_name}' {'enabled' if enabled else 'disabled'}.",
            source=self._config.get_effective_plugin_source(plugin_name),
            config=dict(plugin_table.get("config", {})),
        )

    def configure_plugin(
        self,
        plugin_name: str,
        config_values: dict[str, Any],
    ) -> PluginMutationResult:
        """Persist project-level plugin configuration values."""
        project_cfg = self._load_project_config()
        plugin_table = self._plugin_table(project_cfg, plugin_name)
        plugin_table["enabled"] = plugin_table.get("enabled", True)
        config_table = plugin_table.setdefault("config", {})
        config_table.update(config_values)
        self._write_project_config(project_cfg)
        return PluginMutationResult(
            plugin_name=plugin_name,
            changed=True,
            message=f"Plugin '{plugin_name}' configured.",
            source=self._config.get_effective_plugin_source(plugin_name),
            config=dict(config_table),
        )

    def set_dev_source(self, plugin_name: str, path: str) -> PluginMutationResult:
        """Persist a user-local development source override for a plugin."""
        resolved_path = str(Path(path).expanduser().resolve())
        self._config.set_global_plugin_source(
            plugin_name,
            channel=PluginChannel.DEV_LOCAL,
            path=resolved_path,
        )
        return PluginMutationResult(
            plugin_name=plugin_name,
            changed=True,
            message=f"Development source configured for '{plugin_name}'.",
            source={"channel": PluginChannel.DEV_LOCAL, "path": resolved_path},
        )

    def clear_dev_source(self, plugin_name: str) -> PluginMutationResult:
        """Remove a user-local development source override for a plugin."""
        self._config.clear_global_plugin_source(plugin_name)
        return PluginMutationResult(
            plugin_name=plugin_name,
            changed=True,
            message=f"Development source removed for '{plugin_name}'.",
            source=self._config.get_effective_plugin_source(plugin_name),
        )

    def _load_project_config(self) -> dict[str, Any]:
        path = self._project_config_path()
        if not path.exists():
            return {}

        with open(path, "rb") as file:
            return tomli.load(file)

    def _write_project_config(self, data: dict[str, Any]) -> None:
        path = self._project_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as file:
            tomli_w.dump(data, file)

    def _project_config_path(self) -> Path:
        return self._config.project_config_path or (
            self._config.project_root / ".titan" / "config.toml"
        )

    def _plugin_table(
        self,
        project_cfg: dict[str, Any],
        plugin_name: str,
    ) -> dict[str, Any]:
        plugins_table = project_cfg.setdefault("plugins", {})
        return plugins_table.setdefault(plugin_name, {})
