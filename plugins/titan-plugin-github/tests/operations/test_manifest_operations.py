from titan_plugin_github.models.review_enums import CommentContextKind, FileChangeStatus
from titan_plugin_github.models.view import UIComment, UICommentThread, UIFileChange
from titan_plugin_github.models.review_models import ExistingCommentIndexEntry, Finding
from titan_plugin_github.models.review_enums import FindingSeverity
from titan_plugin_github.models.validators import is_duplicate
from titan_plugin_github.operations.manifest_operations import (
    build_change_manifest,
    build_comment_review_context,
    build_existing_comments_index,
)


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


def test_build_comment_review_context_filters_wiz_html_comments():
    bot_like_comment = UIComment(
        id=4,
        body='<a><picture><source media="(prefers-color-scheme: dark)" srcset="https://assets.wiz.io/wiz-code/long_severity_tags/low_dark.svg"></picture></a>',
        author_login="security-scanner",
        author_name="Scanner",
        formatted_date="2026-01-03",
        path=None,
        line=None,
    )
    thread = UICommentThread(
        thread_id="general_4",
        main_comment=bot_like_comment,
        replies=[],
        is_resolved=False,
        is_outdated=False,
    )

    context = build_comment_review_context([], [thread], max_entries=5, max_chars=1000)

    assert context == []


def test_build_comment_review_context_skips_adjudicated_resolved_threads():
    main = UIComment(
        id=10,
        body="This change may lose non-string analytics values.",
        author_login="reviewer",
        author_name="Reviewer",
        formatted_date="2026-01-01",
        path="src/api.py",
        line=10,
    )
    reply = UIComment(
        id=11,
        body="Everything here is stringly typed by design.",
        author_login="author",
        author_name="Author",
        formatted_date="2026-01-02",
        path="src/api.py",
        line=10,
    )
    thread = UICommentThread(
        thread_id="t2",
        main_comment=main,
        replies=[reply],
        is_resolved=True,
        is_outdated=False,
    )

    context = build_comment_review_context([thread], [], max_entries=5, max_chars=1000)
    index = build_existing_comments_index([thread], [])

    assert context == []
    assert index[0].is_adjudicated is True
    assert index[0].has_author_reply is True


def test_build_comment_review_context_filters_non_bug_like_review_comments():
    design_comment = UIComment(
        id=12,
        body="One suggestion regarding this: this is going to be a bit of a pain if we keep adding events here.",
        author_login="reviewer",
        author_name="Reviewer",
        formatted_date="2026-01-01",
        path="src/api.py",
        line=20,
    )
    thread = UICommentThread(
        thread_id="t4",
        main_comment=design_comment,
        replies=[],
        is_resolved=False,
        is_outdated=False,
    )

    context = build_comment_review_context([thread], [], max_entries=5, max_chars=1000)
    index = build_existing_comments_index([thread], [])

    assert context == []
    assert len(index) == 1


def test_build_comment_review_context_keeps_bug_like_comments():
    bug_comment = UIComment(
        id=13,
        body="This branch maps view_item to select_item, so the tracker UI will show the wrong event type.",
        author_login="reviewer",
        author_name="Reviewer",
        formatted_date="2026-01-01",
        path="src/api.py",
        line=30,
    )
    thread = UICommentThread(
        thread_id="t5",
        main_comment=bug_comment,
        replies=[],
        is_resolved=False,
        is_outdated=False,
    )

    context = build_comment_review_context([thread], [], max_entries=5, max_chars=1000)

    assert len(context) == 1
    assert context[0].path == "src/api.py"


def test_is_duplicate_matches_adjudicated_resolved_thread_more_aggressively():
    finding = Finding(
        severity=FindingSeverity.IMPORTANT,
        category="functional_correctness",
        path="src/api.py",
        line=10,
        title="Serializer drops non-string analytics values",
        why="Why",
        evidence="bundle.getString(k)",
        suggested_comment="Comment",
    )
    existing = ExistingCommentIndexEntry(
        comment_id=1,
        thread_id="t3",
        is_resolved=True,
        path="src/api.py",
        line=10,
        category="functional_correctness",
        title="This change may lose non-string analytics values",
        author="reviewer",
        has_author_reply=True,
        last_reply_author="author",
        reply_count=1,
        is_adjudicated=True,
    )

    assert is_duplicate(finding, existing) is True
