"""Titan CLI Firebase plugin."""

from __future__ import annotations

from titan_cli.core.config import TitanConfig
from titan_cli.core.plugins.plugin_base import TitanPlugin
from titan_cli.core.secrets import SecretManager

from .client import FirebaseClient
from .config import FirebasePluginConfig
from .exceptions import FirebaseClientError, FirebaseConfigurationError


class FirebasePlugin(TitanPlugin):
    """Titan CLI plugin for Firebase operations."""

    @property
    def name(self) -> str:
        return "firebase"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return "Provides Firebase ADC auth and Remote Config access."

    @property
    def dependencies(self) -> list[str]:
        return []

    def initialize(self, config: TitanConfig, secrets: SecretManager) -> None:
        """Initialize the Firebase client from merged Titan plugin config."""
        plugin_config_data = self._get_plugin_config(config)
        try:
            validated_config = FirebasePluginConfig(**plugin_config_data)
        except ValueError as exc:
            raise FirebaseConfigurationError(str(exc)) from exc

        self._client = FirebaseClient(config=validated_config)

    def _get_plugin_config(self, config: TitanConfig) -> dict:
        """Extract Firebase plugin configuration from Titan config."""
        if "firebase" not in config.config.plugins:
            return {}

        plugin_entry = config.config.plugins["firebase"]
        return plugin_entry.config if hasattr(plugin_entry, "config") else {}

    def get_config_schema(self) -> dict:
        """Return the Firebase plugin JSON configuration schema."""
        return FirebasePluginConfig.model_json_schema()

    def is_available(self) -> bool:
        """Return whether Firebase ADC access is available."""
        return hasattr(self, "_client") and self._client is not None and self._client.is_available()

    def get_client(self) -> FirebaseClient:
        """Return the initialized Firebase client."""
        if not hasattr(self, "_client") or self._client is None:
            raise FirebaseClientError(
                "FirebasePlugin not initialized. Firebase client may not be available."
            )
        return self._client

    def get_steps(self) -> dict:
        """Return public workflow steps for the Firebase plugin."""
        from .steps import (
            execute_firebase_login_step,
            execute_firebase_remoteconfig_get_step,
            execute_firebase_status_step,
        )

        return {
            "firebase_login": execute_firebase_login_step,
            "firebase_status": execute_firebase_status_step,
            "firebase_remoteconfig_get": execute_firebase_remoteconfig_get_step,
        }
