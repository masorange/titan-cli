"""Slack SDK compatibility layer used by the Slack client and services."""

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:  # pragma: no cover - exercised implicitly in repo-level tests
    class WebClient:  # type: ignore[override]
        """Small fallback used until the plugin dependency is installed."""

        def __init__(self, token: str, timeout: int | None = None):
            self.token = token
            self.timeout = timeout

    class SlackApiError(Exception):
        """Fallback Slack API error used when slack-sdk is unavailable."""

        def __init__(self, message: str, response=None):
            super().__init__(message)
            self.response = response


__all__ = ["WebClient", "SlackApiError"]
