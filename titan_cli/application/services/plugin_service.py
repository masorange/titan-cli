"""Plugin-oriented application services."""

from __future__ import annotations

from titan_cli.core.config import TitanConfig


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

