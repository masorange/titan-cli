"""Migration manager for config schema upgrades."""

from __future__ import annotations

from copy import deepcopy

from .base import (
    CURRENT_CONFIG_VERSION,
    LEGACY_VERSION,
    ConfigMigration,
    MigrationResult,
)
from .legacy_to_v1 import LegacyToV1Migration


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
