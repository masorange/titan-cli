from pathlib import Path
from typing import Optional

from titan_cli.core.config import TitanConfig
from titan_cli.core.plugins.models import SlackPluginConfig
from titan_cli.core.plugins.plugin_base import TitanPlugin
from titan_cli.core.secrets import SecretManager

from .clients.slack_client import SlackClient
from .config import build_project_slack_token_key
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
        if not plugin_config_data:
            raise SlackConfigurationError(
                "Slack is enabled for this project but no Slack project configuration was found. Configure Slack in this repository first."
            )

        validated_config = SlackPluginConfig(**plugin_config_data)

        project_name = config.get_project_name()
        token_key = build_project_slack_token_key(project_name)

        user_token = secrets.get(token_key)
        if not user_token:
            raise SlackConfigurationError(
                f"Slack user token not found for project '{project_name}'. Configure Slack for this repository first."
            )

        self._client = SlackClient(
            user_token=user_token,
            team_id=validated_config.default_team_id,
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
        from .steps import (
            ai_summarize_messages_step,
            ensure_target_conversation_step,
            list_public_channels_step,
            list_users_step,
            open_direct_message_step,
            prepare_message_destination_step,
            post_message_step,
            prompt_message_body_step,
            read_recent_messages_step,
            select_target_step,
            select_channel_target_step,
            select_user_target_step,
            validate_connection_step,
        )

        return {
            "validate_connection": validate_connection_step,
            "list_public_channels": list_public_channels_step,
            "list_users": list_users_step,
            "select_user_target": select_user_target_step,
            "select_channel_target": select_channel_target_step,
            "select_target": select_target_step,
            "prepare_message_destination": prepare_message_destination_step,
            "ensure_target_conversation": ensure_target_conversation_step,
            "read_recent_messages": read_recent_messages_step,
            "ai_summarize_messages": ai_summarize_messages_step,
            "open_direct_message": open_direct_message_step,
            "prompt_message_body": prompt_message_body_step,
            "post_message": post_message_step,
        }

    @property
    def workflows_path(self) -> Optional[Path]:
        """Return the plugin workflows directory path."""
        return Path(__file__).parent / "workflows"
