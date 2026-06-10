from unittest.mock import MagicMock

import pytest

from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_slack.clients import slack_client as slack_client_module
from titan_plugin_slack.clients.slack_client import SlackClient
from titan_plugin_slack.exceptions import SlackClientError
from titan_plugin_slack.models import UISlackAuth


def test_slack_client_requires_user_token() -> None:
    with pytest.raises(SlackClientError):
        SlackClient(user_token="")


def test_slack_client_stores_user_token() -> None:
    client = SlackClient(user_token="xoxp-test-token", team_id="T123", timeout=45)

    assert client.user_token == "xoxp-test-token"
    assert client.team_id == "T123"
    assert client.timeout == 45
    assert client.web_client is not None


def test_slack_client_auth_test_returns_identity_fields() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.web_client = MagicMock()
    client.auth_service = MagicMock()
    client.auth_service.auth_test.return_value = ClientSuccess(
        data=UISlackAuth(
            user_id="U123",
            team_id="T123",
            team="Acme",
            url="https://acme.slack.com",
            bot_id=None,
        )
    )

    result = client.auth_test()

    assert isinstance(result, ClientSuccess)
    assert result.data.user_id == "U123"
    assert result.data.team_id == "T123"


def test_slack_client_auth_test_returns_client_error_for_invalid_token() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.auth_service = MagicMock()
    client.auth_service.auth_test.return_value = ClientError(
        error_message="Slack auth failed: invalid_auth",
        error_code="AUTH_ERROR",
    )

    result = client.auth_test()

    assert isinstance(result, ClientError)
    assert result.error_message == "Slack auth failed: invalid_auth"


def test_slack_client_auth_test_returns_client_error_for_transport_failure() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.auth_service = MagicMock()
    client.auth_service.auth_test.return_value = ClientError(
        error_message="Slack auth request failed: network down",
        error_code="AUTH_REQUEST_ERROR",
    )

    result = client.auth_test()

    assert isinstance(result, ClientError)
    assert result.error_message == "Slack auth request failed: network down"


def test_list_users_maps_members_and_cursor() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.directory_service = MagicMock()
    client.directory_service.list_users.return_value = ClientSuccess(
        data=(
            [
                slack_client_module.UISlackUser(id="U123", name="alex", real_name="Alex"),
                slack_client_module.UISlackUser(
                    id="U456", name="bot-user", real_name="Bot User", is_bot=True, is_active=False
                ),
            ],
            "cursor-123",
        )
    )

    result = client.list_users(limit=50)

    assert isinstance(result, ClientSuccess)
    users, next_cursor = result.data
    assert next_cursor == "cursor-123"
    assert len(users) == 2
    assert users[0].id == "U123"
    assert users[0].real_name == "Alex"
    assert users[0].is_active is True
    assert users[1].is_bot is True
    assert users[1].real_name == "Bot User"
    assert users[1].is_active is False


def test_list_users_returns_client_error() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.directory_service = MagicMock()
    client.directory_service.list_users.return_value = ClientError(
        error_message="Slack list_users failed: missing_scope",
        error_code="LIST_USERS_ERROR",
    )

    result = client.list_users()

    assert isinstance(result, ClientError)
    assert result.error_message == "Slack list_users failed: missing_scope"


def test_list_public_channels_maps_channels_and_cursor() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.directory_service = MagicMock()
    client.directory_service.list_public_channels.return_value = ClientSuccess(
        data=(
            [
                slack_client_module.UISlackChannel(id="C123", name="general"),
                slack_client_module.UISlackChannel(id="C456", name="announcements"),
            ],
            "cursor-456",
        )
    )

    result = client.list_public_channels(limit=25)

    assert isinstance(result, ClientSuccess)
    channels, next_cursor = result.data
    assert next_cursor == "cursor-456"
    assert len(channels) == 2
    assert channels[0].id == "C123"
    assert channels[0].name == "general"
    assert channels[1].is_private is False


def test_list_public_channels_returns_client_error() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.directory_service = MagicMock()
    client.directory_service.list_public_channels.return_value = ClientError(
        error_message="Slack list_public_channels failed: missing_scope",
        error_code="LIST_PUBLIC_CHANNELS_ERROR",
    )

    result = client.list_public_channels()

    assert isinstance(result, ClientError)
    assert result.error_message == "Slack list_public_channels failed: missing_scope"


def test_read_channel_maps_messages_and_pagination() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.conversation_service = MagicMock()
    client.conversation_service.read_conversation.return_value = ClientSuccess(
        data=(
            [
                slack_client_module.UISlackMessage(
                    ts="123.456",
                    text="Hello",
                    user="U123",
                    thread_ts="123.456",
                    reply_count=2,
                ),
                slack_client_module.UISlackMessage(
                    ts="123.789",
                    text="World",
                    user="U456",
                    reply_count=0,
                ),
            ],
            "cursor-789",
            True,
        )
    )

    result = client.read_channel("C123", limit=10)

    assert isinstance(result, ClientSuccess)
    messages, next_cursor, has_more = result.data
    assert next_cursor == "cursor-789"
    assert has_more is True
    assert len(messages) == 2
    assert messages[0].ts == "123.456"
    assert messages[0].thread_ts == "123.456"
    assert messages[0].reply_count == 2
    assert messages[1].text == "World"


def test_read_channel_returns_client_error() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.conversation_service = MagicMock()
    client.conversation_service.read_conversation.return_value = ClientError(
        error_message="Slack read_channel failed: channel_not_found",
        error_code="READ_CHANNEL_ERROR",
    )

    result = client.read_channel("C404")

    assert isinstance(result, ClientError)
    assert result.error_message == "Slack read_channel failed: channel_not_found"


def test_search_users_delegates_to_directory_service() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.directory_service = MagicMock()
    client.directory_service.search_users.return_value = ClientSuccess(data=[])

    result = client.search_users("alex", max_matches=5, page_size=50, max_pages=3)

    assert isinstance(result, ClientSuccess)
    client.directory_service.search_users.assert_called_once_with(
        "alex",
        max_matches=5,
        page_size=50,
        max_pages=3,
    )


def test_search_public_channels_delegates_to_directory_service() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.directory_service = MagicMock()
    client.directory_service.search_public_channels.return_value = ClientSuccess(data=[])

    result = client.search_public_channels(
        "eng",
        max_matches=5,
        page_size=50,
        max_pages=3,
        exclude_archived=False,
    )

    assert isinstance(result, ClientSuccess)
    client.directory_service.search_public_channels.assert_called_once_with(
        "eng",
        max_matches=5,
        page_size=50,
        max_pages=3,
        exclude_archived=False,
    )


def test_open_direct_message_delegates_to_conversation_service() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.conversation_service = MagicMock()
    client.conversation_service.open_direct_message.return_value = ClientSuccess(data=MagicMock())

    result = client.open_direct_message("U123")

    assert isinstance(result, ClientSuccess)
    client.conversation_service.open_direct_message.assert_called_once_with("U123")


def test_post_message_delegates_to_message_service() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.message_service = MagicMock()
    client.message_service.post_message.return_value = ClientSuccess(data=MagicMock())

    result = client.post_message("D123", "Hello", thread_ts="123.456")

    assert isinstance(result, ClientSuccess)
    client.message_service.post_message.assert_called_once_with(
        "D123", "Hello", thread_ts="123.456"
    )
