from types import SimpleNamespace
from unittest.mock import Mock

from titan_cli.core.result import ClientError, ClientSuccess

from titan_plugin_github.steps.code_review_steps import _filter_invalid_inline_comments


def test_filter_invalid_inline_comments_keeps_only_github_valid_ones():
    github = Mock()
    github.create_draft_review.side_effect = [
        ClientSuccess(data=101, message="ok"),
        ClientError(error_message="HTTP 422 invalid comment", error_code="API_ERROR"),
    ]
    github.delete_review.return_value = ClientSuccess(data=None, message="deleted")
    ctx = SimpleNamespace(github=github)

    payload = {
        "commit_id": "abc123",
        "comments": [
            {"path": "src/a.py", "line": 10, "side": "RIGHT", "body": "valid"},
            {"path": "src/b.py", "line": 20, "side": "RIGHT", "body": "invalid"},
        ],
        "body": "general body",
    }

    filtered_payload, rejected = _filter_invalid_inline_comments(ctx, 42, payload)

    assert filtered_payload["comments"] == [payload["comments"][0]]
    assert filtered_payload["body"] == "general body"
    assert len(rejected) == 1
    assert rejected[0]["path"] == "src/b.py"
    github.delete_review.assert_called_once_with(42, 101)
