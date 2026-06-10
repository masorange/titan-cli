import pytest

from titan_plugin_slack.clients.slack_client import SlackClient
from titan_plugin_slack.exceptions import SlackClientError


def test_slack_client_requires_bot_token() -> None:
    with pytest.raises(SlackClientError):
        SlackClient(bot_token="")


def test_slack_client_stores_token() -> None:
    client = SlackClient(bot_token="xoxb-test-token")

    assert client.bot_token == "xoxb-test-token"
    assert client.web_client is not None
