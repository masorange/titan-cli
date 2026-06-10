import pytest

from titan_plugin_slack.clients.slack_client import SlackClient
from titan_plugin_slack.exceptions import SlackClientError


def test_slack_client_requires_bot_token() -> None:
    with pytest.raises(SlackClientError):
        SlackClient(user_token="")


def test_slack_client_stores_user_token() -> None:
    client = SlackClient(user_token="xoxp-test-token", team_id="T123", timeout=45)

    assert client.user_token == "xoxp-test-token"
    assert client.team_id == "T123"
    assert client.timeout == 45
    assert client.web_client is not None
