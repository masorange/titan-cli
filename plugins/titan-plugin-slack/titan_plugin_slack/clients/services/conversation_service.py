"""Internal service for Slack conversation history operations."""

from titan_cli.core.result import ClientError, ClientSuccess, ClientResult

from ..sdk import SlackApiError
from ...models import NetworkSlackMessage, UISlackMessage


class ConversationService:
    """Service for Slack conversation and history access."""

    def __init__(self, web_client):
        self.web_client = web_client

    @staticmethod
    def _build_api_error(exc: SlackApiError, operation: str) -> ClientError:
        error_code = "unknown_error"
        response = getattr(exc, "response", None)
        if isinstance(response, dict):
            error_code = response.get("error", error_code)
        elif hasattr(response, "data") and isinstance(response.data, dict):
            error_code = response.data.get("error", error_code)
        return ClientError(
            error_message=f"Slack {operation} failed: {error_code}",
            error_code="READ_CHANNEL_ERROR",
            details={"slack_error": error_code},
        )

    @staticmethod
    def _map_message(message: dict) -> NetworkSlackMessage:
        return NetworkSlackMessage(
            ts=message.get("ts", ""),
            text=message.get("text", ""),
            user=message.get("user"),
            thread_ts=message.get("thread_ts"),
            reply_count=message.get("reply_count", 0),
            subtype=message.get("subtype"),
        )

    @staticmethod
    def _to_ui_message(message: NetworkSlackMessage) -> UISlackMessage:
        return UISlackMessage(
            ts=message.ts,
            text=message.text,
            user=message.user,
            thread_ts=message.thread_ts,
            reply_count=message.reply_count,
            subtype=message.subtype,
        )

    def read_conversation(
        self,
        conversation_id: str,
        limit: int = 20,
        cursor: str | None = None,
        oldest: str | None = None,
        latest: str | None = None,
        inclusive: bool = False,
    ) -> ClientResult[tuple[list[UISlackMessage], str | None, bool]]:
        """Read message history from a Slack conversation."""
        try:
            response = self.web_client.conversations_history(
                channel=conversation_id,
                limit=limit,
                cursor=cursor,
                oldest=oldest,
                latest=latest,
                inclusive=inclusive,
            )
        except SlackApiError as exc:
            return self._build_api_error(exc, "read_channel")
        except Exception as exc:
            if hasattr(exc, "response"):
                return self._build_api_error(exc, "read_channel")
            return ClientError(
                error_message=f"Slack channel history request failed: {exc}",
                error_code="READ_CHANNEL_REQUEST_ERROR",
            )

        if not response.get("ok", False):
            return ClientError(
                error_message=f"Slack read_channel failed: {response.get('error', 'unknown_error')}",
                error_code="READ_CHANNEL_ERROR",
            )

        messages = [self._map_message(message) for message in response.get("messages", [])]
        ui_messages = [self._to_ui_message(message) for message in messages]
        next_cursor = response.get("response_metadata", {}).get("next_cursor") or None
        has_more = response.get("has_more", False)
        return ClientSuccess(
            data=(ui_messages, next_cursor, has_more),
            message=f"Retrieved {len(ui_messages)} Slack messages",
        )
