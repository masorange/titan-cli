from titan_plugin_github.models.review_enums import FindingSeverity, ReviewActionSource, ReviewActionType
from titan_plugin_github.models.review_models import Finding, ReviewActionProposal
from titan_plugin_github.operations.review_action_operations import (
    build_new_comment_actions,
    build_review_action_payload,
    extract_diff_hunk_for_action,
)


DIFF = """\
diff --git a/src/foo.py b/src/foo.py
index abc..def 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -10,6 +10,7 @@
 def hello():
     print(\"hello\")
+    print(\"world\")
     return True
"""


def test_build_new_comment_actions_keeps_anchor_data():
    finding = Finding(
        severity=FindingSeverity.IMPORTANT,
        category="functional_correctness",
        path="src/foo.py",
        line=999,
        title="Test finding",
        why="Why",
        evidence='print("world")',
        snippet='print("world")',
        suggested_comment="Comment",
    )

    actions = build_new_comment_actions([finding])

    assert actions[0].anchor_snippet == 'print("world")'
    assert actions[0].evidence == 'print("world")'


def test_build_review_action_payload_resolves_line_from_snippet():
    action = ReviewActionProposal(
        action_type=ReviewActionType.NEW_COMMENT,
        source=ReviewActionSource.NEW_FINDING,
        path="src/foo.py",
        line=999,
        title="Test",
        body="Comment body",
        reasoning="Why",
        anchor_snippet='print("world")',
        evidence='print("world")',
    )

    payload = build_review_action_payload([action], commit_sha="abc123", diff=DIFF)

    assert payload["comments"][0]["line"] == 12
    assert "body" not in payload


def test_extract_diff_hunk_for_action_returns_none_without_resolved_anchor():
    action = ReviewActionProposal(
        action_type=ReviewActionType.NEW_COMMENT,
        source=ReviewActionSource.NEW_FINDING,
        path="src/foo.py",
        line=999,
        title="Test",
        body="Comment body",
        reasoning="Why",
        anchor_snippet="missing_snippet",
        evidence="missing_snippet",
    )

    assert extract_diff_hunk_for_action(action, DIFF) is None
