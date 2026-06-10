from unittest.mock import MagicMock

import pytest

from titan_plugin_slack.clients import slack_client as slack_client_module
from titan_plugin_slack.clients.slack_client import SlackClient
from titan_plugin_slack.exceptions import SlackAPIError, SlackClientError


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
    client.web_client.auth_test.return_value = {
        "ok": True,
        "user_id": "U123",
        "team_id": "T123",
        "team": "Acme",
        "url": "https://acme.slack.com",
        "bot_id": None,
    }

    result = client.auth_test()

    assert result == {
        "user_id": "U123",
        "team_id": "T123",
        "team": "Acme",
        "url": "https://acme.slack.com",
        "bot_id": None,
    }


def test_slack_client_auth_test_raises_api_error_for_invalid_token(monkeypatch) -> None:
    class FakeSlackApiError(Exception):
        def __init__(self, message: str, response=None):
            super().__init__(message)
            self.response = response

    monkeypatch.setattr(slack_client_module, "SlackApiError", FakeSlackApiError)

    client = SlackClient(user_token="xoxp-test-token")
    client.web_client = MagicMock()
    client.web_client.auth_test.side_effect = FakeSlackApiError(
        "invalid auth",
        response={"error": "invalid_auth"},
    )

    with pytest.raises(SlackAPIError, match="Slack auth failed: invalid_auth"):
        client.auth_test()


def test_slack_client_auth_test_raises_client_error_for_transport_failure() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.web_client = MagicMock()
    client.web_client.auth_test.side_effect = RuntimeError("network down")

    with pytest.raises(SlackClientError, match="Slack auth request failed: network down"):
        client.auth_test()


def test_list_users_maps_members_and_cursor() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.web_client = MagicMock()
    client.web_client.users_list.return_value = {
        "ok": True,
        "members": [
            {
                "id": "U123",
                "name": "alex",
                "real_name": "Alex",
                "is_bot": False,
                "deleted": False,
            },
            {
                "id": "U456",
                "name": "bot-user",
                "profile": {"real_name": "Bot User"},
                "is_bot": True,
                "deleted": True,
            },
        ],
        "response_metadata": {"next_cursor": "cursor-123"},
    }

    users, next_cursor = client.list_users(limit=50)

    assert next_cursor == "cursor-123"
    assert len(users) == 2
    assert users[0].id == "U123"
    assert users[0].real_name == "Alex"
    assert users[0].is_active is True
    assert users[1].is_bot is True
    assert users[1].real_name == "Bot User"
    assert users[1].is_active is False


def test_list_users_raises_api_error() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.web_client = MagicMock()
    client.web_client.users_list.return_value = {"ok": False, "error": "missing_scope"}

    with pytest.raises(SlackAPIError, match="Slack list_users failed: missing_scope"):
        client.list_users()


def test_list_public_channels_maps_channels_and_cursor() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.web_client = MagicMock()
    client.web_client.conversations_list.return_value = {
        "ok": True,
        "channels": [
            {"id": "C123", "name": "general", "is_channel": True, "is_private": False},
            {"id": "C456", "name": "announcements", "is_channel": True, "is_private": False},
        ],
        "response_metadata": {"next_cursor": "cursor-456"},
    }

    channels, next_cursor = client.list_public_channels(limit=25)

    assert next_cursor == "cursor-456"
    assert len(channels) == 2
    assert channels[0].id == "C123"
    assert channels[0].name == "general"
    assert channels[1].is_private is False


def test_list_public_channels_raises_api_error() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.web_client = MagicMock()
    client.web_client.conversations_list.return_value = {
        "ok": False,
        "error": "missing_scope",
    }

    with pytest.raises(
        SlackAPIError, match="Slack list_public_channels failed: missing_scope"
    ):
        client.list_public_channels()


def test_read_channel_maps_messages_and_pagination() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.web_client = MagicMock()
    client.web_client.conversations_history.return_value = {
        "ok": True,
        "messages": [
            {
                "ts": "123.456",
                "text": "Hello",
                "user": "U123",
                "thread_ts": "123.456",
                "reply_count": 2,
                "subtype": None,
            },
            {
                "ts": "123.789",
                "text": "World",
                "user": "U456",
                "reply_count": 0,
            },
        ],
        "has_more": True,
        "response_metadata": {"next_cursor": "cursor-789"},
    }

    messages, next_cursor, has_more = client.read_channel("C123", limit=10)

    assert next_cursor == "cursor-789"
    assert has_more is True
    assert len(messages) == 2
    assert messages[0].ts == "123.456"
    assert messages[0].thread_ts == "123.456"
    assert messages[0].reply_count == 2
    assert messages[1].text == "World"


def test_read_channel_raises_api_error() -> None:
    client = SlackClient(user_token="xoxp-test-token")
    client.web_client = MagicMock()
    client.web_client.conversations_history.return_value = {
        "ok": False,
        "error": "channel_not_found",
    }

    with pytest.raises(SlackAPIError, match="Slack read_channel failed: channel_not_found"):
        client.read_channel("C404")
