"""Unit tests for the unified-diff mapper."""
from titan_plugin_git.models.mappers import from_unified_diff

MODIFIED = """diff --git a/a.py b/a.py
index 111..222 100644
--- a/a.py
+++ b/a.py
@@ -1,3 +1,4 @@ def f():
 keep
-old
+new
+extra
 tail
@@ -10,2 +11,2 @@
 ctx
-gone
\\ No newline at end of file
+here
"""


def test_hunks_carry_header_and_line_numbers():
    diff = from_unified_diff(MODIFIED, "a.py")

    assert [h.header for h in diff.hunks] == ["@@ -1,3 +1,4 @@ def f():", "@@ -10,2 +11,2 @@"]
    first = [(line.kind, line.text, line.old_no, line.new_no) for line in diff.hunks[0].lines]
    assert first == [
        ("context", "keep", 1, 1),
        ("del", "old", 2, None),
        ("add", "new", None, 2),
        ("add", "extra", None, 3),
        ("context", "tail", 3, 4),
    ]
    assert (diff.additions, diff.deletions) == (3, 2)


def test_no_newline_marker_is_a_line_without_numbers():
    diff = from_unified_diff(MODIFIED, "a.py")

    marker = diff.hunks[1].lines[2]
    assert (marker.kind, marker.text, marker.old_no, marker.new_no) == ("no_newline", "No newline at end of file", None, None)
    assert diff.hunks[1].lines[3].new_no == 12


def test_empty_input_is_no_hunks():
    diff = from_unified_diff("", "a.py")

    assert diff.hunks == [] and not diff.is_binary


def test_binary_patch_is_marked_without_hunks():
    diff = from_unified_diff("diff --git a/x.png b/x.png\nBinary files a/x.png and b/x.png differ\n", "x.png")

    assert diff.is_binary and diff.hunks == []


def test_line_starting_with_dashes_inside_a_hunk_is_a_deletion():
    diff = from_unified_diff("@@ -1,2 +1,1 @@\n--- not a header\n keep\n", "a.md")

    assert [line.kind for line in diff.hunks[0].lines] == ["del", "context"]
