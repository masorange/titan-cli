"""The review material as files in the worktree: layout and content."""

from titan_plugin_github.models.review_models import PullRequestManifest
from titan_plugin_github.models.view import UIComment, UICommentThread
from titan_plugin_github.operations.review_material_operations import (
    annotate_diff_hunk,
    base_file_path,
    diff_file_path,
    read_file_content,
    render_file_diff,
    render_pr_file,
)

PR = PullRequestManifest(
    number=7, title="Migrate API", base="main", head="feat", author="a", description="Moves X to Y."
)


def test_paths_live_in_a_hidden_folder_so_a_plain_search_skips_them():
    assert diff_file_path("src/a.py") == ".titan-review/diffs/src/a.py.diff"
    assert base_file_path("src/a.py") == ".titan-review/base/src/a.py"


def test_a_hunk_numbers_added_and_context_lines_by_the_new_file():
    hunk = "@@ -10,2 +10,3 @@\n def bar():\n+    return 1\n-    return 0"

    result = annotate_diff_hunk(hunk)

    assert result.splitlines()[0] == "@@ -10,2 +10,3 @@"
    assert "10 [CONTEXT] def bar():" in result
    assert "11 [ADDED]     return 1" in result
    assert "[DELETED]     return 0" in result
    assert annotate_diff_hunk("") == ""


def test_added_and_deleted_lines_that_look_like_file_headers_keep_the_numbering():
    hunk = "@@ -5,2 +5,3 @@\n+++x\n--- sql comment\n+after"

    result = annotate_diff_hunk(hunk)

    assert " 5 [ADDED] ++x" in result
    assert "[DELETED] -- sql comment" in result
    assert " 6 [ADDED] after" in result


def test_a_file_diff_is_numbered_like_the_prompt_was_so_anchors_still_work():
    rendered = render_file_diff("a.py", ["@@ -1,2 +1,2 @@\n context\n-old\n+new\n"])

    assert rendered.startswith("# a.py")
    assert "1 [CONTEXT] context" in rendered
    assert "[DELETED] old" in rendered
    assert "2 [ADDED] new" in rendered
    assert "(no textual diff)" in render_file_diff("img.png", [])


def _comment(body: str, author: str = "rev", path=None, line=None) -> UIComment:
    return UIComment(
        id=1, body=body, author_login=author, author_name=author,
        formatted_date="01/10/2026 10:00:00", path=path, line=line,
    )


def test_the_pr_file_carries_the_claim_and_every_comment_in_full():
    long_body = "None dereferenced when the default is empty. " * 20
    threads = [
        UICommentThread(
            thread_id="t1",
            main_comment=_comment(long_body, path="a.py", line=3),
            replies=[_comment("Fixed in abc.", author="author")],
            is_resolved=True,
            is_outdated=False,
        ),
        UICommentThread(
            thread_id="t2",
            main_comment=_comment("nit: rename this", path="b.py", line=9),
            replies=[],
            is_resolved=False,
            is_outdated=True,
        ),
    ]
    general = [
        UICommentThread(
            thread_id="g1", main_comment=_comment("Looks good overall"), replies=[],
            is_resolved=False, is_outdated=False,
        )
    ]

    text = render_pr_file(PR, threads, general, "abc123")

    assert "# PR #7: Migrate API" in text
    assert "Moves X to Y." in text
    assert "abc123" in text
    # Whole, resolved ones and nits included: the summary of eight cut at 220 chars is gone.
    assert long_body.strip() in text
    assert "### [resolved] a.py:3" in text
    assert "@author:\nFixed in abc." in text
    assert "### [open, outdated] b.py:9" in text
    assert "nit: rename this" in text
    assert "## General comments" in text
    assert "Looks good overall" in text


def test_a_pr_without_comments_says_so():
    assert "(none)" in render_pr_file(PR, [], [], None)


def test_read_file_content_reads_a_file_and_returns_none_otherwise(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")

    assert read_file_content("a.py", str(tmp_path)) == "x = 1\n"
    assert read_file_content("missing.py", str(tmp_path)) is None
