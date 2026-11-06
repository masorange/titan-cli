from pathlib import Path
from typing import Optional

from titan_cli.core.config import TitanConfig
from titan_cli.core.logging import get_logger
from titan_cli.core.plugins.models import SlackPluginConfig
from titan_cli.core.plugins.plugin_base import TitanPlugin
from titan_cli.core.security import OAuthCredentials, SecretBroker

from .clients.slack_client import SlackClient
from .config import SLACK_OAUTH, build_project_slack_oauth_key, slack_oauth_app
from .exceptions import SlackClientError, SlackConfigurationError
from .screens.slack_config_screen import SlackConfigScreen

logger = get_logger(__name__)


class SlackPlugin(TitanPlugin):
    """Titan CLI plugin for Slack operations."""

    @property
    def titan_requires(self) -> str:
        # Must stay in sync with the titan-cli dependency in this plugin's
        # pyproject.toml; a repo test enforces the pairing.
        return ">=0.8.0"

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

    def initialize(self, config: TitanConfig, broker: SecretBroker) -> None:
        """Initialize the Slack client from the current user's OAuth grant."""
        plugin_config_data = self._get_plugin_config(config)
        if not plugin_config_data:
            raise SlackConfigurationError(
                "Slack is enabled for this project but no Slack project configuration was found. Configure Slack in this repository first."
            )

        validated_config = SlackPluginConfig(**plugin_config_data)
        project_name = config.get_project_name()
        grant_key = build_project_slack_oauth_key(project_name)

        if not broker.exists(grant_key):
            raise SlackConfigurationError(
                f"Slack user token not found for project '{project_name}'. Configure Slack for this repository first."
            )
        if not validated_config.oauth_client_id:
            raise SlackConfigurationError(
                "Slack project configuration has no OAuth client ID. Reconfigure Slack for this repository."
            )

        credentials = OAuthCredentials(
            broker, grant_key, SLACK_OAUTH, slack_oauth_app(validated_config.oauth_client_id)
        )
        # The access token (refreshed first when about to expire) crosses into
        # the client constructor; Titan keeps the refresh token.
        self._client = credentials.create_client(
            lambda user_token: SlackClient(
                user_token=user_token,
                team_id=validated_config.default_team_id,
                default_channels=validated_config.default_channels,
                token_refresher=credentials.refresh,
            )
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
            format_markdown_message_step,
            list_public_channels_step,
            list_users_step,
            open_direct_message_step,
            prepare_message_destination_step,
            post_message_step,
            prompt_message_body_step,
            read_recent_messages_step,
            select_target_step,
            select_channel_target_step,
            select_default_or_search_channel_target_step,
            select_user_target_step,
            upload_file_step,
            validate_connection_step,
        )

        return {
            "validate_connection": validate_connection_step,
            "list_public_channels": list_public_channels_step,
            "list_users": list_users_step,
            "select_user_target": select_user_target_step,
            "select_channel_target": select_channel_target_step,
            "select_default_or_search_channel_target": select_default_or_search_channel_target_step,
            "select_target": select_target_step,
            "prepare_message_destination": prepare_message_destination_step,
            "ensure_target_conversation": ensure_target_conversation_step,
            "read_recent_messages": read_recent_messages_step,
            "ai_summarize_messages": ai_summarize_messages_step,
            "open_direct_message": open_direct_message_step,
            "format_markdown_message": format_markdown_message_step,
            "prompt_message_body": prompt_message_body_step,
            "post_message": post_message_step,
            "upload_file": upload_file_step,
        }

    @property
    def workflows_path(self) -> Optional[Path]:
        """Return the plugin workflows directory path."""
        return Path(__file__).parent / "workflows"
