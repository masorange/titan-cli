"""Minimal Slack client baseline for the first plugin phase."""

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

from ..exceptions import SlackAPIError, SlackClientError


class SlackClient:
    """Small Slack client wrapper used by the Slack plugin."""

    def __init__(self, user_token: str, team_id: str | None = None, timeout: int = 30):
        if not user_token:
            raise SlackClientError("Slack client requires a user token.")

        self.user_token = user_token
        self.team_id = team_id
        self.timeout = timeout
        self.web_client = WebClient(token=user_token, timeout=timeout)

    def auth_test(self) -> dict:
        """Validate the configured user token with Slack auth.test."""
        try:
            response = self.web_client.auth_test()
        except SlackApiError as exc:
            error_code = "unknown_error"
            response = getattr(exc, "response", None)
            if isinstance(response, dict):
                error_code = response.get("error", error_code)
            raise SlackAPIError(f"Slack auth failed: {error_code}") from exc
        except Exception as exc:
            raise SlackClientError(f"Slack auth request failed: {exc}") from exc

        if not response.get("ok", False):
            raise SlackAPIError(
                f"Slack auth failed: {response.get('error', 'unknown_error')}"
            )

        return {
            "user_id": response.get("user_id"),
            "team_id": response.get("team_id"),
            "team": response.get("team"),
            "url": response.get("url"),
            "bot_id": response.get("bot_id"),
        }
