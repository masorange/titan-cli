"""Titan CLI Firebase plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from titan_cli.core.plugins.plugin_base import TitanPlugin

from .clients.firebase_client import FirebaseClient
from .config import FirebasePluginConfig
from .exceptions import FirebaseConfigurationError, FirebaseError


class FirebasePlugin(TitanPlugin):
    """
    Titan CLI plugin for Firebase Remote Config.

    Authentication is Application Default Credentials, so the plugin takes no
    credential of its own: `initialize` receives a secret broker like every
    plugin does and deliberately never uses it.
    """

    @property
    def name(self) -> str:
        return "firebase"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return "Reads and publishes Firebase Remote Config parameters."

    @property
    def dependencies(self) -> list[str]:
        return []

    def initialize(self, config: Any, broker: Any) -> None:
        """
        Build the Firebase client from the merged plugin configuration.

        Does no I/O: credentials are resolved on the first network call, so
        enabling the plugin never waits on gcloud.
        """
        try:
            validated_config = FirebasePluginConfig(**self._get_plugin_config(config))
        except ValueError as exc:
            raise FirebaseConfigurationError(str(exc)) from exc

        self._client = FirebaseClient(validated_config)

    def _get_plugin_config(self, config: Any) -> Dict[str, Any]:
        """Extract the firebase section from the Titan configuration."""
        plugins = getattr(getattr(config, "config", None), "plugins", None)
        if not plugins or "firebase" not in plugins:
            return {}
        entry = plugins["firebase"]
        return getattr(entry, "config", {}) or {}

    def get_config_schema(self) -> dict:
        """Return the JSON schema for the plugin configuration screen."""
        schema = FirebasePluginConfig.model_json_schema()
        properties = schema.get("properties", {})
        preferred_order = [
            "default_project",
            "quota_project_id",
            "api_base_url",
            "request_timeout",
            "oauth_scopes",
        ]
        ordered = {
            field: properties[field]
            for field in preferred_order
            if field in properties
        }
        ordered.update(
            {
                field: value
                for field, value in properties.items()
                if field not in ordered
            }
        )
        schema["properties"] = ordered
        return schema

    def is_available(self) -> bool:
        """Return whether the client was built."""
        return getattr(self, "_client", None) is not None

    def get_client(self) -> FirebaseClient:
        """Return the initialized Firebase client."""
        client = getattr(self, "_client", None)
        if client is None:
            raise FirebaseError(
                "FirebasePlugin no está inicializado; el cliente de Firebase "
                "no está disponible."
            )
        return client

    def get_steps(self) -> dict:
        """Return the plugin's public workflow steps."""
        from .steps.auth_check_step import execute_firebase_auth_check_step
        from .steps.conditions_step import (
            execute_firebase_remoteconfig_conditions_step,
        )
        from .steps.diff_step import execute_firebase_remoteconfig_diff_step
        from .steps.fanout_plan_step import (
            execute_firebase_remoteconfig_fanout_plan_step,
        )
        from .steps.fanout_publish_step import (
            execute_firebase_remoteconfig_fanout_publish_step,
        )
        from .steps.publish_step import execute_firebase_remoteconfig_publish_step
        from .steps.remoteconfig_get_step import (
            execute_firebase_remoteconfig_get_step,
        )
        from .steps.select_key_step import (
            execute_firebase_remoteconfig_select_key_step,
        )
        from .steps.select_target_step import execute_firebase_select_target_step
        from .steps.select_targets_step import execute_firebase_select_targets_step
        from .steps.set_value_step import (
            execute_firebase_remoteconfig_set_value_step,
        )

        return {
            "firebase_auth_check": execute_firebase_auth_check_step,
            "firebase_select_target": execute_firebase_select_target_step,
            "firebase_remoteconfig_get": execute_firebase_remoteconfig_get_step,
            "firebase_remoteconfig_conditions": (
                execute_firebase_remoteconfig_conditions_step
            ),
            "firebase_remoteconfig_select_key": (
                execute_firebase_remoteconfig_select_key_step
            ),
            "firebase_remoteconfig_set_value": (
                execute_firebase_remoteconfig_set_value_step
            ),
            "firebase_remoteconfig_diff": execute_firebase_remoteconfig_diff_step,
            "firebase_remoteconfig_publish": (
                execute_firebase_remoteconfig_publish_step
            ),
            "firebase_select_targets": execute_firebase_select_targets_step,
            "firebase_remoteconfig_fanout_plan": (
                execute_firebase_remoteconfig_fanout_plan_step
            ),
            "firebase_remoteconfig_fanout_publish": (
                execute_firebase_remoteconfig_fanout_publish_step
            ),
        }

    @property
    def workflows_path(self) -> Optional[Path]:
        """Return the plugin workflows directory."""
        return Path(__file__).parent / "workflows"
