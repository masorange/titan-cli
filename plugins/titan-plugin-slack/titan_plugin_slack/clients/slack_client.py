"""Slack client facade backed by internal services."""

from . import sdk as slack_sdk_module
from .services import (
    AuthService,
    ConversationService,
    DirectoryService,
    IdentityResolver,
    MessageService,
)
from titan_cli.core.result import ClientResult

from ..exceptions import SlackClientError
from ..models import (
    UISlackAuth,
    UISlackChannel,
    UISlackConversation,
    UISlackMessage,
    UISlackPostedMessage,
    UISlackUser,
)

SlackApiError = slack_sdk_module.SlackApiError
WebClient = slack_sdk_module.WebClient


class SlackClient:
    """Slack client facade used by the Slack plugin."""

    def __init__(self, user_token: str, team_id: str | None = None, timeout: int = 30):
        if not user_token:
            raise SlackClientError("Slack client requires a user token.")

        self.user_token = user_token
        self.team_id = team_id
        self.timeout = timeout
        self._web_client = WebClient(token=user_token, timeout=timeout)

        self.auth_service = AuthService(self._web_client)
        self.directory_service = DirectoryService(self._web_client)
        self.conversation_service = ConversationService(self._web_client)
        self.identity_resolver = IdentityResolver(self._web_client)
        self.message_service = MessageService(self._web_client)

    @property
    def web_client(self):
        """Expose the underlying Slack WebClient for compatibility and testing."""
        return self._web_client

    @web_client.setter
    def web_client(self, value) -> None:
        """Keep internal services aligned when tests or callers replace the WebClient."""
        self._web_client = value
        self.auth_service.web_client = value
        self.directory_service.web_client = value
        self.conversation_service.web_client = value
        self.identity_resolver.web_client = value
        self.message_service.web_client = value

    def auth_test(self) -> ClientResult[UISlackAuth]:
        """Validate the configured user token with Slack auth.test."""
        return self.auth_service.auth_test()

    def list_users(
        self, limit: int = 100, cursor: str | None = None
    ) -> ClientResult[tuple[list[UISlackUser], str | None]]:
        """List Slack users visible to the current token."""
        return self.directory_service.list_users(limit=limit, cursor=cursor)

    def list_public_channels(
        self,
        limit: int = 100,
        cursor: str | None = None,
        exclude_archived: bool = True,
    ) -> ClientResult[tuple[list[UISlackChannel], str | None]]:
        """List public Slack channels visible to the current token."""
        return self.directory_service.list_public_channels(
            limit=limit,
            cursor=cursor,
            exclude_archived=exclude_archived,
        )

    def search_users(
        self,
        query: str,
        *,
        max_matches: int = 20,
        page_size: int = 200,
        max_pages: int = 50,
    ) -> ClientResult[list[UISlackUser]]:
        """Search Slack users across multiple pages of visible users."""
        return self.directory_service.search_users(
            query,
            max_matches=max_matches,
            page_size=page_size,
            max_pages=max_pages,
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
        """Search public Slack channels across multiple pages of visible channels."""
        return self.directory_service.search_public_channels(
            query,
            max_matches=max_matches,
            page_size=page_size,
            max_pages=max_pages,
            exclude_archived=exclude_archived,
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
        """Search accessible public and private Slack channels."""
        return self.directory_service.search_channels(
            query,
            max_matches=max_matches,
            page_size=page_size,
            max_pages=max_pages,
            exclude_archived=exclude_archived,
        )

    def read_channel(
        self,
        channel_id: str,
        limit: int = 20,
        cursor: str | None = None,
        oldest: str | None = None,
        latest: str | None = None,
        inclusive: bool = False,
    ) -> ClientResult[tuple[list[UISlackMessage], str | None, bool]]:
        """Read message history from a Slack public channel."""
        return self.conversation_service.read_conversation(
            conversation_id=channel_id,
            limit=limit,
            cursor=cursor,
            oldest=oldest,
            latest=latest,
            inclusive=inclusive,
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
        """Read message history from any Slack conversation ID."""
        return self.conversation_service.read_conversation(
            conversation_id=conversation_id,
            limit=limit,
            cursor=cursor,
            oldest=oldest,
            latest=latest,
            inclusive=inclusive,
        )

    def open_direct_message(self, user_id: str) -> ClientResult[UISlackConversation]:
        """Open or reuse a direct message conversation with a Slack user."""
        return self.conversation_service.open_direct_message(user_id)

    def get_user(self, user_id: str) -> ClientResult[UISlackUser]:
        """Resolve a Slack user by ID."""
        return self.identity_resolver.get_user(user_id)

    def get_channel(self, channel_id: str) -> ClientResult[UISlackChannel]:
        """Resolve a Slack channel by ID."""
        return self.identity_resolver.get_channel(channel_id)

    def post_message(
        self,
        channel_id: str,
        text: str,
        *,
        thread_ts: str | None = None,
    ) -> ClientResult[UISlackPostedMessage]:
        """Post a plain-text message to a Slack conversation."""
        return self.message_service.post_message(channel_id, text, thread_ts=thread_ts)
