from unittest.mock import MagicMock

from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_slack.clients.services.message_service import MessageService


def test_post_message_returns_posted_message() -> None:
    web_client = MagicMock()
    web_client.chat_postMessage.return_value = {
        "ok": True,
        "channel": "D123",
        "ts": "123.456",
        "message": {"text": "Hello there", "thread_ts": None},
    }

    service = MessageService(web_client)

    result = service.post_message("D123", "Hello there")

    assert isinstance(result, ClientSuccess)
    assert result.data.channel == "D123"
    assert result.data.ts == "123.456"
    assert result.data.text == "Hello there"


def test_post_message_returns_client_error_on_api_failure() -> None:
    web_client = MagicMock()
    web_client.chat_postMessage.return_value = {"ok": False, "error": "missing_scope"}

    service = MessageService(web_client)

    result = service.post_message("D123", "Hello there")

    assert isinstance(result, ClientError)
    assert result.error_message == "Slack post_message failed: missing_scope"


def test_upload_file_returns_uploaded_file() -> None:
    web_client = MagicMock()
    web_client.files_upload_v2.return_value = {
        "ok": True,
        "files": [{"id": "F123", "title": "Report", "name": "report.pdf", "permalink": "https://slack/F123"}],
    }

    service = MessageService(web_client)

    result = service.upload_file("C123", "/tmp/report.pdf", title="Report", initial_comment="Here it is")

    assert isinstance(result, ClientSuccess)
    assert result.data.file_id == "F123"
    assert result.data.channel == "C123"
    assert result.data.title == "Report"
    assert result.data.permalink == "https://slack/F123"
    web_client.files_upload_v2.assert_called_once_with(
        channel="C123",
        file="/tmp/report.pdf",
        title="Report",
        initial_comment="Here it is",
        thread_ts=None,
    )


def test_upload_file_returns_client_error_on_api_failure() -> None:
    web_client = MagicMock()
    web_client.files_upload_v2.return_value = {"ok": False, "error": "missing_scope", "needed": "files:write"}

    service = MessageService(web_client)

    result = service.upload_file("C123", "/tmp/report.pdf")

    assert isinstance(result, ClientError)
    assert result.error_code == "UPLOAD_FILE_ERROR"
    assert "files:write" in result.error_message


def test_upload_file_returns_client_error_when_file_unreadable() -> None:
    web_client = MagicMock()
    web_client.files_upload_v2.side_effect = FileNotFoundError("missing")

    service = MessageService(web_client)

    result = service.upload_file("C123", "/tmp/missing.pdf")

    assert isinstance(result, ClientError)
    assert result.error_code == "UPLOAD_FILE_READ_ERROR"
