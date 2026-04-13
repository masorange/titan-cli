"""Configuration schema migrations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol


LEGACY_VERSION = "legacy"
CURRENT_CONFIG_VERSION = "1.0"


class ConfigMigration(Protocol):
    """Protocol for a single config migration step."""

    from_version: str
    to_version: str

    def migrate(self, data: dict) -> dict:
        """Return migrated config data."""


@dataclass(frozen=True)
class MigrationResult:
    """Result returned by the migration manager."""

    data: dict
    original_version: str
    final_version: str
    applied_steps: list[str]
    changed: bool


class LegacyToV1Migration:
    """Migrate legacy config files to schema version 1.0."""

    from_version = LEGACY_VERSION
    to_version = CURRENT_CONFIG_VERSION

    def migrate(self, data: dict) -> dict:
        migrated = deepcopy(data)
        migrated.pop("version", None)
        migrated["config_version"] = CURRENT_CONFIG_VERSION

        ai_cfg = migrated.get("ai")
        if not isinstance(ai_cfg, dict):
            return migrated

        default_connection = ai_cfg.pop("default", None)
        if default_connection and "default_connection" not in ai_cfg:
            ai_cfg["default_connection"] = default_connection

        legacy_providers = ai_cfg.pop("providers", None)
        if isinstance(legacy_providers, dict):
            connections = ai_cfg.setdefault("connections", {})
            migrated_connections = self._migrate_connections(
                legacy_providers,
                default_connection=ai_cfg.get("default_connection"),
            )
            for connection_id, provider_cfg in migrated_connections.items():
                if connection_id in connections:
                    continue
                connections[connection_id] = provider_cfg

        return migrated

    def _migrate_connections(
        self,
        legacy_providers: dict,
        default_connection: str | None,
    ) -> dict:
        gateway_groups: dict[str, list[tuple[str, dict]]] = {}
        direct_connections: dict[str, dict] = {}

        for connection_id, provider_cfg in legacy_providers.items():
            if self._is_gateway_provider(provider_cfg):
                base_url = provider_cfg.get("base_url")
                if base_url:
                    gateway_groups.setdefault(base_url, []).append(
                        (connection_id, provider_cfg)
                    )
                    continue

            direct_connections[connection_id] = self._migrate_direct_connection(
                provider_cfg
            )

        migrated = {**direct_connections}
        for entries in gateway_groups.values():
            connection_id, connection_cfg = self._merge_gateway_group(
                entries,
                default_connection=default_connection,
            )
            migrated[connection_id] = connection_cfg

        return migrated

    def _is_gateway_provider(self, provider_cfg: dict) -> bool:
        legacy_type = provider_cfg.get("type")
        legacy_provider = provider_cfg.get("provider")
        return legacy_provider == "custom" or (
            legacy_type == "corporate" and bool(provider_cfg.get("base_url"))
        )

    def _migrate_direct_connection(self, provider_cfg: dict) -> dict:
        migrated = deepcopy(provider_cfg)
        migrated["default_model"] = migrated.pop("model", None)
        migrated.pop("type", None)
        migrated["kind"] = "direct_provider"
        return migrated

    def _merge_gateway_group(
        self,
        entries: list[tuple[str, dict]],
        default_connection: str | None,
    ) -> tuple[str, dict]:
        selected_id, selected_cfg = entries[0]
        if default_connection:
            for candidate_id, candidate_cfg in entries:
                if candidate_id == default_connection:
                    selected_id, selected_cfg = candidate_id, candidate_cfg
                    break

        merged = deepcopy(selected_cfg)
        merged["default_model"] = merged.pop("model", None)
        merged.pop("type", None)
        merged.pop("provider", None)
        merged["kind"] = "gateway"
        merged["gateway_type"] = "openai_compatible"
        return selected_id, merged


class MigrationManager:
    """Apply config migrations until the target version is reached."""

    def __init__(
        self,
        migrations: list[ConfigMigration] | None = None,
        target_version: str = CURRENT_CONFIG_VERSION,
    ) -> None:
        if migrations is None:
            migrations = [LegacyToV1Migration()]
        self._migrations = migrations
        self._target_version = target_version
        self._migration_map = {
            migration.from_version: migration for migration in self._migrations
        }

    def detect_version(self, data: dict) -> str:
        """Return the schema version for raw config data."""
        version = data.get("config_version")
        if isinstance(version, str) and version.strip():
            return version
        return LEGACY_VERSION

    def migrate(self, data: dict) -> MigrationResult:
        """Migrate raw config data to the configured target version."""
        migrated = deepcopy(data)
        original_version = self.detect_version(migrated)
        current_version = original_version
        applied_steps: list[str] = []

        while current_version != self._target_version:
            migration = self._migration_map.get(current_version)
            if migration is None:
                raise ValueError(
                    f"No config migration path from '{current_version}' "
                    f"to '{self._target_version}'."
                )

            migrated = migration.migrate(migrated)
            applied_steps.append(f"{migration.from_version}->{migration.to_version}")
            current_version = migration.to_version

        return MigrationResult(
            data=migrated,
            original_version=original_version,
            final_version=current_version,
            applied_steps=applied_steps,
            changed=bool(applied_steps),
        )
