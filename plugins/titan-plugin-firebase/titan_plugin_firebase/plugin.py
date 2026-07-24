"""Titan CLI Firebase plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from titan_cli.core.config import TitanConfig
from titan_cli.core.oauth import OAuthManager
from titan_cli.core.plugins.plugin_base import TitanPlugin
from titan_cli.core.secrets import SecretManager

from .client import (
    FirebaseClient,
    OAUTH_CLIENT_ID_SECRET_KEY,
    OAUTH_CLIENT_SECRET_KEY,
)
from .config import FirebasePluginConfig
from .exceptions import FirebaseClientError, FirebaseConfigurationError
from .oauth import GoogleOAuthFlow, GoogleOAuthProvider


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
        return "Provides Firebase OAuth auth and Remote Config access."

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

        get_project_name = getattr(config, "get_project_name", None)
        project_name = get_project_name() if callable(get_project_name) else None
        if not isinstance(project_name, str) or not project_name.strip():
            project_name = None

        project_oauth_client_id = self._get_saved_oauth_client_id(
            secrets,
            project_name,
            include_generic=False,
        )
        project_oauth_client_secret = self._get_saved_oauth_client_secret(
            secrets,
            project_name,
            include_generic=False,
        )
        generic_oauth_client_id = self._get_saved_oauth_client_id(secrets, None)
        generic_oauth_client_secret = self._get_saved_oauth_client_secret(
            secrets,
            None,
        )

        if project_oauth_client_id:
            oauth_client_id = project_oauth_client_id
            oauth_client_secret = project_oauth_client_secret
        elif validated_config.oauth_client_id:
            oauth_client_id = validated_config.oauth_client_id
            oauth_client_secret = (
                validated_config.oauth_client_secret
                or project_oauth_client_secret
            )
            if (
                oauth_client_secret is None
                and generic_oauth_client_id == oauth_client_id
            ):
                oauth_client_secret = generic_oauth_client_secret
        elif generic_oauth_client_id:
            oauth_client_id = generic_oauth_client_id
            oauth_client_secret = generic_oauth_client_secret
        else:
            oauth_client_id = None
            oauth_client_secret = None
        if oauth_client_id:
            validated_config = validated_config.model_copy(
                update={
                    "oauth_client_id": oauth_client_id,
                    "oauth_client_secret": oauth_client_secret,
                }
            )

        oauth_providers = {}
        if oauth_client_id:
            oauth_providers["google"] = GoogleOAuthProvider(
                GoogleOAuthFlow(
                    client_id=oauth_client_id,
                    client_secret=oauth_client_secret,
                    redirect_port=validated_config.oauth_redirect_port,
                    scopes=validated_config.oauth_scopes,
                    timeout=validated_config.oauth_timeout,
                    token_request_timeout=validated_config.request_timeout,
                )
            )

        self._client = FirebaseClient(
            config=validated_config,
            secrets=secrets,
            project_name=project_name,
            oauth_manager=OAuthManager(secrets, providers=oauth_providers),
        )

    def _get_plugin_config(self, config: TitanConfig) -> dict:
        """Extract Firebase plugin configuration from Titan config."""
        if "firebase" not in config.config.plugins:
            return {}

        plugin_entry = config.config.plugins["firebase"]
        return plugin_entry.config if hasattr(plugin_entry, "config") else {}

    def _get_saved_oauth_client_id(
        self,
        secrets: SecretManager,
        project_name: Optional[str],
        *,
        include_generic: bool = True,
    ) -> Optional[str]:
        """Return a Google OAuth client ID saved during interactive login."""
        keys = []
        if project_name:
            keys.append(f"{project_name}_{OAUTH_CLIENT_ID_SECRET_KEY}")
        if include_generic:
            keys.append(OAUTH_CLIENT_ID_SECRET_KEY)

        for key in keys:
            value = secrets.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _get_saved_oauth_client_secret(
        self,
        secrets: SecretManager,
        project_name: Optional[str],
        *,
        include_generic: bool = True,
    ) -> Optional[str]:
        """Return a Google OAuth client secret saved during interactive login."""
        keys = []
        if project_name:
            keys.append(f"{project_name}_{OAUTH_CLIENT_SECRET_KEY}")
        if include_generic:
            keys.append(OAUTH_CLIENT_SECRET_KEY)

        for key in keys:
            value = secrets.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def get_config_schema(self) -> dict:
        """Return the Firebase plugin JSON configuration schema."""
        schema = FirebasePluginConfig.model_json_schema()
        properties = schema.get("properties", {})
        preferred_order = [
            "oauth_client_id",
            "oauth_client_secret",
            "oauth_redirect_port",
            "oauth_scopes",
            "oauth_timeout",
            "default_project",
            "default_environment",
            "projects",
            "brand_projects",
            "brand_projects_layout",
            "api_base_url",
            "request_timeout",
            "access_token_env_var",
            "access_token",
        ]
        ordered_properties = {
            field_name: properties[field_name]
            for field_name in preferred_order
            if field_name in properties
        }
        ordered_properties.update(
            {
                field_name: field_info
                for field_name, field_info in properties.items()
                if field_name not in ordered_properties
            }
        )
        schema["properties"] = ordered_properties
        return schema

    def is_available(self) -> bool:
        """Return whether Firebase OAuth access is available."""
        return (
            hasattr(self, "_client")
            and self._client is not None
            and self._client.is_available()
        )

    def get_client(self) -> FirebaseClient:
        """Return the initialized Firebase client."""
        if not hasattr(self, "_client") or self._client is None:
            raise FirebaseClientError(
                "FirebasePlugin not initialized. Firebase client may not be available."
            )
        return self._client

    def get_steps(self) -> dict:
        """Return public workflow steps for the Firebase plugin."""
        from .steps.login_step import (
            execute_firebase_login_step,
            execute_firebase_status_step,
        )
        from .steps.remoteconfig_get_step import execute_firebase_remoteconfig_get_step
        from .steps.remoteconfig_inventory_step import (
            execute_firebase_remoteconfig_inventory_step,
        )

        return {
            "firebase_login": execute_firebase_login_step,
            "firebase_status": execute_firebase_status_step,
            "firebase_remoteconfig_get": execute_firebase_remoteconfig_get_step,
            "firebase_remoteconfig_inventory": (
                execute_firebase_remoteconfig_inventory_step
            ),
        }

    @property
    def workflows_path(self) -> Optional[Path]:
        """Return the plugin workflows directory path."""
        return Path(__file__).parent / "workflows"
