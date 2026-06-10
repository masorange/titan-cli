from pathlib import Path
from typing import Optional

from titan_cli.core.config import TitanConfig
from titan_cli.core.plugins.models import SlackPluginConfig
from titan_cli.core.plugins.plugin_base import TitanPlugin
from titan_cli.core.secrets import SecretManager

from .clients.slack_client import SlackClient
from .exceptions import SlackClientError, SlackConfigurationError
from .screens.slack_config_screen import SlackConfigScreen


class SlackPlugin(TitanPlugin):
    """Titan CLI plugin for Slack operations."""

    @property
    def name(self) -> str:
        return "slack"

    @property
    def description(self) -> str:
        return "Provides Slack messaging and workspace integration."

    @property
    def dependencies(self) -> list[str]:
        return []

    def _get_plugin_config(self, config: TitanConfig) -> dict:
        """Extract Slack plugin configuration."""
        if "slack" not in config.config.plugins:
            return {}

        plugin_entry = config.config.plugins["slack"]
        return plugin_entry.config if hasattr(plugin_entry, "config") else {}

    def get_config_schema(self) -> dict:
        """Return JSON schema for Slack plugin configuration."""
        return SlackPluginConfig.model_json_schema()

    def has_custom_config_screen(self) -> bool:
        """Slack uses a dedicated configuration screen."""
        return True

    def create_config_screen(self, config: TitanConfig) -> SlackConfigScreen:
        """Create the Slack-specific configuration screen."""
        return SlackConfigScreen(config)

    def initialize(self, config: TitanConfig, secrets: SecretManager) -> None:
        """Initialize the Slack client using the current user's personal token."""
        plugin_config_data = self._get_plugin_config(config)
        validated_config = SlackPluginConfig(**plugin_config_data)

        user_token = secrets.get("slack_user_token")
        if not user_token:
            raise SlackConfigurationError(
                "Slack user token not found. Configure Slack and store a personal token in keyring, or set SLACK_USER_TOKEN."
            )

        self._client = SlackClient(
            user_token=user_token,
            team_id=validated_config.default_team_id,
            timeout=validated_config.timeout,
        )

    def is_available(self) -> bool:
        """Return whether the plugin has an initialized client."""
        return hasattr(self, "_client") and self._client is not None

    def get_client(self) -> SlackClient:
        """Return the initialized Slack client instance."""
        if not hasattr(self, "_client") or self._client is None:
            raise SlackClientError(
                "SlackPlugin not initialized. Slack client may not be available."
            )
        return self._client

    def get_steps(self) -> dict:
        """Return public workflow steps for the plugin."""
        return {}

    @property
    def workflows_path(self) -> Optional[Path]:
        """Return the plugin workflows directory path."""
        return Path(__file__).parent / "workflows"
