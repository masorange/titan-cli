"""Legacy-to-v1 config migration."""

from __future__ import annotations

import re
from copy import deepcopy

from .base import CURRENT_CONFIG_VERSION, LEGACY_VERSION


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

        legacy_default_connection = ai_cfg.pop("default", None)
        default_connection = (
            self._normalize_connection_id(legacy_default_connection)
            if legacy_default_connection
            else None
        )
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

        for legacy_connection_id, provider_cfg in legacy_providers.items():
            connection_id = self._normalize_connection_id(legacy_connection_id)

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

    def _normalize_connection_id(self, connection_id: str) -> str:
        """Normalize legacy connection ids to TOML-safe keys."""
        normalized = re.sub(r"[^a-z0-9]+", "-", connection_id.lower()).strip("-")
        if not normalized:
            raise ValueError("Legacy connection ID must contain letters or numbers.")
        return normalized

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
        migrated["connection_type"] = "direct_provider"
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
        merged["connection_type"] = "gateway"
        merged["gateway_backend"] = "openai_compatible"
        return selected_id, merged
