from titan_plugin_github.models.review_models import ReferencedCommitContext, ThreadReviewContext
from titan_plugin_github.operations.thread_resolution_operations import build_thread_resolution_prompt


def test_build_thread_resolution_prompt_includes_referenced_commit_context():
    context = ThreadReviewContext(
        thread_id="thread_123",
        comment_id=10,
        path="src/buttons.kt",
        line=543,
        main_comment_body="Please remove the default dialog state.",
        main_comment_author="reviewer",
        all_replies=[{"author": "author", "body": "Fixed in 343e2e9"}],
        current_code_hunk="@@ -1,2 +1,2 @@\n-old\n+new\n",
        referenced_commits=[
            ReferencedCommitContext(
                sha="343e2e9d7402d0afccfd35a9ecc8e6ea341031c6",
                abbreviated_sha="343e2e9",
                message="remove default state value",
                changed_files=["src/BaseDialog.kt"],
                patch_excerpt="diff --git a/src/BaseDialog.kt b/src/BaseDialog.kt\n@@ -1 +1 @@\n-old\n+new\n",
            )
        ],
    )

    prompt = build_thread_resolution_prompt([context])

    assert "Referenced commits from replies" in prompt
    assert "343e2e9" in prompt
    assert "src/BaseDialog.kt" in prompt
    assert "remove default state value" in prompt
