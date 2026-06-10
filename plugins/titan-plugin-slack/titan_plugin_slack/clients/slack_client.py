"""Minimal Slack client baseline for the first plugin phase."""

try:
    from slack_sdk import WebClient
except ImportError:  # pragma: no cover - exercised implicitly in repo-level tests
    class WebClient:  # type: ignore[override]
        """Small fallback used until the plugin dependency is installed."""

        def __init__(self, token: str, timeout: int | None = None):
            self.token = token
            self.timeout = timeout

from ..exceptions import SlackClientError


class SlackClient:
    """Small Slack client wrapper used by the Slack plugin."""

    def __init__(self, user_token: str, team_id: str | None = None, timeout: int = 30):
        if not user_token:
            raise SlackClientError("Slack client requires a user token.")

        self.user_token = user_token
        self.team_id = team_id
        self.timeout = timeout
        self.web_client = WebClient(token=user_token, timeout=timeout)
