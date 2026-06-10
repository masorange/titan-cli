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
