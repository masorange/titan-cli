from titan_plugin_github.models.review_enums import CommentContextKind, FileChangeStatus
from titan_plugin_github.models.view import UIComment, UICommentThread, UIFileChange
from titan_plugin_github.operations.manifest_operations import build_change_manifest, build_comment_review_context


def test_build_change_manifest_sets_generic_flags(sample_ui_pr):
    files = [
        UIFileChange(
            path="android/app/build.gradle.kts",
            additions=4,
            deletions=1,
            status=FileChangeStatus.MODIFIED,
            status_icon="~",
        ),
        UIFileChange(
            path="ios/Podfile.lock",
            additions=8,
            deletions=2,
            status=FileChangeStatus.MODIFIED,
            status_icon="~",
        ),
        UIFileChange(
            path="docs/architecture.md",
            additions=12,
            deletions=0,
            status=FileChangeStatus.MODIFIED,
            status_icon="~",
        ),
    ]

    manifest = build_change_manifest(sample_ui_pr, files)

    assert manifest.files[0].is_config is True
    assert manifest.files[1].is_lockfile is True
    assert manifest.files[2].is_docs is True


def test_build_comment_review_context_summarizes_long_threads():
    main = UIComment(
        id=1,
        body="There is no validation when parsing the payload and this can crash on null input.",
        author_login="reviewer",
        author_name="Reviewer",
        formatted_date="2026-01-01",
        path="src/api.py",
        line=10,
    )
    reply = UIComment(
        id=2,
        body="I added a guard for null payloads and a regression test in the latest commit.",
        author_login="author",
        author_name="Author",
        formatted_date="2026-01-02",
        path="src/api.py",
        line=10,
    )
    thread = UICommentThread(
        thread_id="t1",
        main_comment=main,
        replies=[reply],
        is_resolved=False,
        is_outdated=False,
    )

    context = build_comment_review_context([thread], [], max_entries=5, max_chars=1000)

    assert len(context) == 1
    assert context[0].kind == CommentContextKind.THREAD_SUMMARY
    assert "Latest reply" in context[0].summary


def test_build_comment_review_context_filters_automated_comments():
    bot_comment = UIComment(
        id=3,
        body="<!-- 0 Errors 5 Warnings --><table><tr><td>Danger report</td></tr></table>",
        author_login="danger[bot]",
        author_name="Danger",
        formatted_date="2026-01-03",
        path=None,
        line=None,
    )
    thread = UICommentThread(
        thread_id="general_3",
        main_comment=bot_comment,
        replies=[],
        is_resolved=False,
        is_outdated=False,
    )

    context = build_comment_review_context([], [thread], max_entries=5, max_chars=1000)

    assert context == []
