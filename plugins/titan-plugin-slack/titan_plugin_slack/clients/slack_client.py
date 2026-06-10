"""Minimal Slack client baseline for the first plugin phase."""

try:
    from slack_sdk import WebClient
except ImportError:  # pragma: no cover - exercised implicitly in repo-level tests
    class WebClient:  # type: ignore[override]
        """Small fallback used until the plugin dependency is installed."""

        def __init__(self, token: str):
            self.token = token

from ..exceptions import SlackClientError
from ..messages import msg


class SlackClient:
    """Small Slack client wrapper used by the Slack plugin."""

    def __init__(self, bot_token: str):
        if not bot_token:
            raise SlackClientError(msg.Slack.CLIENT_REQUIRES_BOT_TOKEN)

        self.bot_token = bot_token
        self.web_client = WebClient(token=bot_token)
