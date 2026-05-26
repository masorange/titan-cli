"""Shared types and constants for config schema migrations."""

from __future__ import annotations

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
