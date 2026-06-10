from pathlib import Path
from typing import Optional

from titan_cli.core.config import TitanConfig
from titan_cli.core.plugins.plugin_base import TitanPlugin
from titan_cli.core.secrets import SecretManager

from .clients.slack_client import SlackClient
from .exceptions import SlackClientError
from .messages import msg


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

    def initialize(self, config: TitanConfig, secrets: SecretManager) -> None:
        """Initialize the Slack client baseline for later configuration work."""
        self._client = SlackClient(bot_token="placeholder-token")

    def is_available(self) -> bool:
        """Return whether the plugin has an initialized client."""
        return hasattr(self, "_client") and self._client is not None

    def get_client(self) -> SlackClient:
        """Return the initialized Slack client instance."""
        if not hasattr(self, "_client") or self._client is None:
            raise SlackClientError(msg.Plugin.SLACK_CLIENT_NOT_AVAILABLE)
        return self._client

    def get_steps(self) -> dict:
        """Return public workflow steps for the plugin."""
        return {}

    @property
    def workflows_path(self) -> Optional[Path]:
        """Return the plugin workflows directory path."""
        return Path(__file__).parent / "workflows"
