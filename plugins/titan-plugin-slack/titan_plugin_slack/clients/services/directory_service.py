"""Internal service for Slack directory and discovery operations."""

from titan_cli.core.result import ClientError, ClientSuccess, ClientResult

from ..sdk import SlackApiError
from ...operations import filter_channels_for_query, filter_users_for_query
from ...models import (
    NetworkSlackChannel,
    NetworkSlackUser,
    UISlackChannel,
    UISlackUser,
)


class DirectoryService:
    """Service for Slack user and public channel discovery."""

    def __init__(self, web_client):
        self.web_client = web_client

    @staticmethod
    def _build_api_error(exc: SlackApiError, operation: str, error_code_name: str) -> ClientError:
        error_code = "unknown_error"
        response = getattr(exc, "response", None)
        if isinstance(response, dict):
            error_code = response.get("error", error_code)
        elif hasattr(response, "data") and isinstance(response.data, dict):
            error_code = response.data.get("error", error_code)
        return ClientError(
            error_message=f"Slack {operation} failed: {error_code}",
            error_code=error_code_name,
            details={"slack_error": error_code},
        )

    @staticmethod
    def _map_user(member: dict) -> NetworkSlackUser:
        profile = member.get("profile", {})
        return NetworkSlackUser(
            id=member.get("id", ""),
            name=member.get("name", ""),
            real_name=(
                member.get("real_name")
                or profile.get("real_name")
                or profile.get("display_name")
            ),
            is_bot=member.get("is_bot", False),
            is_active=not member.get("deleted", False),
        )

    @staticmethod
    def _map_channel(channel: dict) -> NetworkSlackChannel:
        return NetworkSlackChannel(
            id=channel.get("id", ""),
            name=channel.get("name", ""),
            is_channel=channel.get("is_channel", True),
            is_private=channel.get("is_private", False),
        )

    @staticmethod
    def _to_ui_user(user: NetworkSlackUser) -> UISlackUser:
        return UISlackUser(
            id=user.id,
            name=user.name,
            real_name=user.real_name,
            is_bot=user.is_bot,
            is_active=user.is_active,
        )

    @staticmethod
    def _to_ui_channel(channel: NetworkSlackChannel) -> UISlackChannel:
        return UISlackChannel(
            id=channel.id,
            name=channel.name,
            is_channel=channel.is_channel,
            is_private=channel.is_private,
        )

    def list_users(
        self, limit: int = 100, cursor: str | None = None
    ) -> ClientResult[tuple[list[UISlackUser], str | None]]:
        """List Slack users visible to the current token."""
        try:
            response = self.web_client.users_list(limit=limit, cursor=cursor)
        except SlackApiError as exc:
            return self._build_api_error(exc, "list_users", "LIST_USERS_ERROR")
        except Exception as exc:
            if hasattr(exc, "response"):
                return self._build_api_error(exc, "list_users", "LIST_USERS_ERROR")
            return ClientError(
                error_message=f"Slack users request failed: {exc}",
                error_code="LIST_USERS_REQUEST_ERROR",
            )

        if not response.get("ok", False):
            return ClientError(
                error_message=f"Slack list_users failed: {response.get('error', 'unknown_error')}",
                error_code="LIST_USERS_ERROR",
            )

        members = [self._map_user(member) for member in response.get("members", [])]
        ui_users = [self._to_ui_user(member) for member in members]
        next_cursor = response.get("response_metadata", {}).get("next_cursor") or None
        return ClientSuccess(
            data=(ui_users, next_cursor),
            message=f"Retrieved {len(ui_users)} Slack users",
        )

    def list_public_channels(
        self,
        limit: int = 100,
        cursor: str | None = None,
        exclude_archived: bool = True,
    ) -> ClientResult[tuple[list[UISlackChannel], str | None]]:
        """List public Slack channels visible to the current token."""
        try:
            response = self.web_client.conversations_list(
                limit=limit,
                cursor=cursor,
                exclude_archived=exclude_archived,
                types="public_channel",
            )
        except SlackApiError as exc:
            return self._build_api_error(
                exc,
                "list_public_channels",
                "LIST_PUBLIC_CHANNELS_ERROR",
            )
        except Exception as exc:
            if hasattr(exc, "response"):
                return self._build_api_error(
                    exc,
                    "list_public_channels",
                    "LIST_PUBLIC_CHANNELS_ERROR",
                )
            return ClientError(
                error_message=f"Slack conversations request failed: {exc}",
                error_code="LIST_PUBLIC_CHANNELS_REQUEST_ERROR",
            )

        if not response.get("ok", False):
            return ClientError(
                error_message=(
                    "Slack list_public_channels failed: "
                    f"{response.get('error', 'unknown_error')}"
                ),
                error_code="LIST_PUBLIC_CHANNELS_ERROR",
            )

        channels = [self._map_channel(channel) for channel in response.get("channels", [])]
        ui_channels = [self._to_ui_channel(channel) for channel in channels]
        next_cursor = response.get("response_metadata", {}).get("next_cursor") or None
        return ClientSuccess(
            data=(ui_channels, next_cursor),
            message=f"Retrieved {len(ui_channels)} public Slack channels",
        )

    def search_users(
        self,
        query: str,
        *,
        max_matches: int = 20,
        page_size: int = 200,
        max_pages: int = 50,
    ) -> ClientResult[list[UISlackUser]]:
        """Search Slack users by paging through visible users and filtering locally."""
        cursor: str | None = None
        scanned_pages = 0
        collected: list[UISlackUser] = []
        seen_ids: set[str] = set()

        while scanned_pages < max_pages:
            page_result = self.list_users(limit=page_size, cursor=cursor)
            match page_result:
                case ClientSuccess(data=(users, next_cursor)):
                    for user in users:
                        if user.id not in seen_ids:
                            seen_ids.add(user.id)
                            collected.append(user)

                    matches = filter_users_for_query(collected, query, limit=max_matches)
                    if len(matches) >= max_matches or not next_cursor:
                        return ClientSuccess(
                            data=matches,
                            message=f"Found {len(matches)} Slack users for query",
                        )

                    cursor = next_cursor
                    scanned_pages += 1
                case ClientError() as err:
                    return err

        matches = filter_users_for_query(collected, query, limit=max_matches)
        return ClientSuccess(
            data=matches,
            message=f"Found {len(matches)} Slack users for query",
        )

    def search_public_channels(
        self,
        query: str,
        *,
        max_matches: int = 20,
        page_size: int = 200,
        max_pages: int = 50,
        exclude_archived: bool = True,
    ) -> ClientResult[list[UISlackChannel]]:
        """Search Slack public channels by paging through visible channels and filtering locally."""
        cursor: str | None = None
        scanned_pages = 0
        collected: list[UISlackChannel] = []
        seen_ids: set[str] = set()

        while scanned_pages < max_pages:
            page_result = self.list_public_channels(
                limit=page_size,
                cursor=cursor,
                exclude_archived=exclude_archived,
            )
            match page_result:
                case ClientSuccess(data=(channels, next_cursor)):
                    for channel in channels:
                        if channel.id not in seen_ids:
                            seen_ids.add(channel.id)
                            collected.append(channel)

                    matches = filter_channels_for_query(collected, query, limit=max_matches)
                    if len(matches) >= max_matches or not next_cursor:
                        return ClientSuccess(
                            data=matches,
                            message=f"Found {len(matches)} Slack channels for query",
                        )

                    cursor = next_cursor
                    scanned_pages += 1
                case ClientError() as err:
                    return err

        matches = filter_channels_for_query(collected, query, limit=max_matches)
        return ClientSuccess(
            data=matches,
            message=f"Found {len(matches)} Slack channels for query",
        )

    def search_channels(
        self,
        query: str,
        *,
        max_matches: int = 20,
        page_size: int = 200,
        max_pages: int = 50,
        exclude_archived: bool = True,
    ) -> ClientResult[list[UISlackChannel]]:
        """Search accessible public and private Slack channels by paging and filtering locally."""
        cursor: str | None = None
        scanned_pages = 0
        collected: list[UISlackChannel] = []
        seen_ids: set[str] = set()

        while scanned_pages < max_pages:
            try:
                response = self.web_client.conversations_list(
                    limit=page_size,
                    cursor=cursor,
                    exclude_archived=exclude_archived,
                    types="public_channel,private_channel",
                )
            except SlackApiError as exc:
                return self._build_api_error(
                    exc,
                    "search_channels",
                    "SEARCH_CHANNELS_ERROR",
                )
            except Exception as exc:
                if hasattr(exc, "response"):
                    return self._build_api_error(
                        exc,
                        "search_channels",
                        "SEARCH_CHANNELS_ERROR",
                    )
                return ClientError(
                    error_message=f"Slack channel search request failed: {exc}",
                    error_code="SEARCH_CHANNELS_REQUEST_ERROR",
                )

            if not response.get("ok", False):
                return ClientError(
                    error_message=(
                        f"Slack search_channels failed: {response.get('error', 'unknown_error')}"
                    ),
                    error_code="SEARCH_CHANNELS_ERROR",
                )

            channels = [self._map_channel(channel) for channel in response.get("channels", [])]
            ui_channels = [self._to_ui_channel(channel) for channel in channels]

            for channel in ui_channels:
                if channel.id not in seen_ids:
                    seen_ids.add(channel.id)
                    collected.append(channel)

            matches = filter_channels_for_query(collected, query, limit=max_matches)
            next_cursor = response.get("response_metadata", {}).get("next_cursor") or None
            if len(matches) >= max_matches or not next_cursor:
                return ClientSuccess(
                    data=matches,
                    message=f"Found {len(matches)} Slack channels for query",
                )

            cursor = next_cursor
            scanned_pages += 1

        matches = filter_channels_for_query(collected, query, limit=max_matches)
        return ClientSuccess(
            data=matches,
            message=f"Found {len(matches)} Slack channels for query",
        )
