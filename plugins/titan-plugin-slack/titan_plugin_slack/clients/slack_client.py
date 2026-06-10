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
from ..models import NetworkSlackChannel, NetworkSlackMessage, NetworkSlackUser


class SlackClient:
    """Small Slack client wrapper used by the Slack plugin."""

    def __init__(self, user_token: str, team_id: str | None = None, timeout: int = 30):
        if not user_token:
            raise SlackClientError("Slack client requires a user token.")

        self.user_token = user_token
        self.team_id = team_id
        self.timeout = timeout
        self.web_client = WebClient(token=user_token, timeout=timeout)

    def _handle_api_error(self, exc: SlackApiError, operation: str) -> None:
        """Convert Slack SDK API errors into plugin-level exceptions."""
        error_code = "unknown_error"
        response = getattr(exc, "response", None)
        if isinstance(response, dict):
            error_code = response.get("error", error_code)
        raise SlackAPIError(f"Slack {operation} failed: {error_code}") from exc

    def _map_user(self, member: dict) -> NetworkSlackUser:
        """Normalize a Slack user payload into the plugin model."""
        return NetworkSlackUser(
            id=member.get("id", ""),
            name=member.get("name", ""),
            real_name=member.get("real_name") or member.get("profile", {}).get("real_name"),
            is_bot=member.get("is_bot", False),
            is_active=not member.get("deleted", False),
        )

    def _map_channel(self, channel: dict) -> NetworkSlackChannel:
        """Normalize a Slack conversation payload into the plugin model."""
        return NetworkSlackChannel(
            id=channel.get("id", ""),
            name=channel.get("name", ""),
            is_channel=channel.get("is_channel", True),
            is_private=channel.get("is_private", False),
        )

    def _map_message(self, message: dict) -> NetworkSlackMessage:
        """Normalize a Slack message payload into the plugin model."""
        return NetworkSlackMessage(
            ts=message.get("ts", ""),
            text=message.get("text", ""),
            user=message.get("user"),
            thread_ts=message.get("thread_ts"),
            reply_count=message.get("reply_count", 0),
            subtype=message.get("subtype"),
        )

    def auth_test(self) -> dict:
        """Validate the configured user token with Slack auth.test."""
        try:
            response = self.web_client.auth_test()
        except SlackApiError as exc:
            self._handle_api_error(exc, "auth")
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

    def list_users(
        self, limit: int = 100, cursor: str | None = None
    ) -> tuple[list[NetworkSlackUser], str | None]:
        """List Slack users visible to the current token."""
        try:
            response = self.web_client.users_list(limit=limit, cursor=cursor)
        except SlackApiError as exc:
            self._handle_api_error(exc, "list_users")
        except Exception as exc:
            raise SlackClientError(f"Slack users request failed: {exc}") from exc

        if not response.get("ok", False):
            raise SlackAPIError(
                f"Slack list_users failed: {response.get('error', 'unknown_error')}"
            )

        members = [self._map_user(member) for member in response.get("members", [])]
        next_cursor = response.get("response_metadata", {}).get("next_cursor") or None
        return members, next_cursor

    def list_public_channels(
        self,
        limit: int = 100,
        cursor: str | None = None,
        exclude_archived: bool = True,
    ) -> tuple[list[NetworkSlackChannel], str | None]:
        """List public Slack channels visible to the current token."""
        try:
            response = self.web_client.conversations_list(
                limit=limit,
                cursor=cursor,
                exclude_archived=exclude_archived,
                types="public_channel",
            )
        except SlackApiError as exc:
            self._handle_api_error(exc, "list_public_channels")
        except Exception as exc:
            raise SlackClientError(f"Slack conversations request failed: {exc}") from exc

        if not response.get("ok", False):
            raise SlackAPIError(
                "Slack list_public_channels failed: "
                f"{response.get('error', 'unknown_error')}"
            )

        channels = [self._map_channel(channel) for channel in response.get("channels", [])]
        next_cursor = response.get("response_metadata", {}).get("next_cursor") or None
        return channels, next_cursor

    def read_channel(
        self,
        channel_id: str,
        limit: int = 20,
        cursor: str | None = None,
        oldest: str | None = None,
        latest: str | None = None,
        inclusive: bool = False,
    ) -> tuple[list[NetworkSlackMessage], str | None, bool]:
        """Read message history from a Slack public channel."""
        try:
            response = self.web_client.conversations_history(
                channel=channel_id,
                limit=limit,
                cursor=cursor,
                oldest=oldest,
                latest=latest,
                inclusive=inclusive,
            )
        except SlackApiError as exc:
            self._handle_api_error(exc, "read_channel")
        except Exception as exc:
            raise SlackClientError(f"Slack channel history request failed: {exc}") from exc

        if not response.get("ok", False):
            raise SlackAPIError(
                f"Slack read_channel failed: {response.get('error', 'unknown_error')}"
            )

        messages = [self._map_message(message) for message in response.get("messages", [])]
        next_cursor = response.get("response_metadata", {}).get("next_cursor") or None
        has_more = response.get("has_more", False)
        return messages, next_cursor, has_more
