"""PoEditor plugin for Titan CLI."""

from pathlib import Path

from pydantic import ValidationError

from titan_cli.core.config import TitanConfig
from titan_cli.core.plugins.models import PoEditorPluginConfig
from titan_cli.core.plugins.plugin_base import TitanPlugin
from titan_cli.core.secrets import SecretManager

from .clients import PoEditorClient
from .exceptions import PoEditorClientError, PoEditorConfigurationError


class PoEditorPlugin(TitanPlugin):
    """Titan CLI Plugin for PoEditor operations.

    Provides a PoEditorClient for interacting with PoEditor API.
    """

    @property
    def name(self) -> str:
        return "poeditor"

    @property
    def description(self) -> str:
        return "Provides PoEditor API integration for localization management."

    @property
    def dependencies(self) -> list[str]:
        return []  # No dependencies - PoEditor is standalone

    def initialize(self, config: TitanConfig, secrets: SecretManager) -> None:
        """Initialize plugin with configuration and secrets.

        Configuration cascade (project overrides global):
            1. Global config (~/.titan/config.toml): api_token, timeout
            2. Project settings (.titan/config.toml): default_project_id (optional)

        Reads API token from secrets:
            POEDITOR_API_TOKEN or poeditor_api_token

        Args:
            config: Titan configuration
            secrets: Secret manager for API token

        Raises:
            PoEditorConfigurationError: If configuration is invalid or token is missing
        """
        # Get plugin-specific configuration (already merged by TitanConfig)
        plugin_config_data = self._get_plugin_config(config)

        # Validate configuration using Pydantic model
        try:
            validated_config = PoEditorPluginConfig(**plugin_config_data)
        except ValidationError as e:
            raise PoEditorConfigurationError(str(e)) from e

        # Get API token from secrets (try multiple keys for compatibility)
        api_token = secrets.get("poeditor_api_token") or secrets.get(
            "POEDITOR_API_TOKEN"
        )

        if not api_token:
            raise PoEditorConfigurationError(
                "PoEditor API token not found in secrets. "
                "Please configure with: titan configure --plugin poeditor"
            )

        # Initialize client
        self._client = PoEditorClient(api_token=api_token, timeout=validated_config.timeout)

    def _get_plugin_config(self, config: TitanConfig) -> dict:
        """Extract plugin-specific configuration.

        Args:
            config: Titan configuration

        Returns:
            Plugin configuration dictionary
        """
        if "poeditor" not in config.config.plugins:
            return {}

        plugin_entry = config.config.plugins["poeditor"]
        return plugin_entry.config if hasattr(plugin_entry, "config") else {}

    def get_config_schema(self) -> dict:
        """Return JSON schema for plugin configuration.

        Returns:
            JSON schema for PoEditorPluginConfig
        """
        return PoEditorPluginConfig.model_json_schema()

    def is_available(self) -> bool:
        """Check if PoEditor client is initialized.

        Returns:
            True if client is initialized and available
        """
        return hasattr(self, "_client") and self._client is not None

    def get_client(self) -> PoEditorClient:
        """Returns the initialized PoEditorClient instance.

        Returns:
            PoEditorClient instance

        Raises:
            PoEditorClientError: If client is not available
        """
        if not self.is_available():
            raise PoEditorClientError("PoEditor client not available")
        return self._client

    def get_steps(self) -> dict:
        """Returns a dictionary of available workflow steps.

        Returns:
            Dictionary mapping step names to step functions
        """
        from .steps import (
            import_translations_step,
            list_projects_step,
            select_project_step,
        )

        return {
            "list_projects_step": list_projects_step,
            "select_project_step": select_project_step,
            "import_translations_step": import_translations_step,
        }

    @property
    def workflows_path(self) -> Path | None:
        """Returns the path to the workflows directory.

        Returns:
            Path to workflows directory
        """
        return Path(__file__).parent / "workflows"
