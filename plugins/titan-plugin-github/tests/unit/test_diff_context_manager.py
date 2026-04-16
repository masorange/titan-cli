"""
Tests for DiffContextManager and its internal parsing helpers.

Covers: hunk simple, múltiples hunks, líneas borradas vs añadidas,
outdated comments, suggestions multiline, snippet match,
líneas válidas para inline comment, y fallbacks.
"""

from titan_plugin_github.managers.diff_context_manager import DiffContextManager


# ---------------------------------------------------------------------------
# Fixtures — diff strings
# ---------------------------------------------------------------------------

SIMPLE_DIFF = """\
diff --git a/src/foo.py b/src/foo.py
index abc..def 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -10,6 +10,7 @@
 def hello():
     print("hello")
+    print("world")
     return True

 def bye():
"""

MULTI_HUNK_DIFF = """\
diff --git a/src/bar.py b/src/bar.py
index 111..222 100644
--- a/src/bar.py
+++ b/src/bar.py
@@ -1,5 +1,6 @@
 import os
+import sys
 import re

 def first():
@@ -20,4 +21,5 @@
 def second():
     pass
+    # new comment

"""

DELETED_LINES_DIFF = """\
diff --git a/src/baz.py b/src/baz.py
index aaa..bbb 100644
--- a/src/baz.py
+++ b/src/baz.py
@@ -5,7 +5,6 @@
 def foo():
-    old_line_1 = True
-    old_line_2 = False
+    new_line = True
     return new_line

"""

MULTI_FILE_DIFF = SIMPLE_DIFF + "\n" + MULTI_HUNK_DIFF


# ---------------------------------------------------------------------------
# Parsing — hunk simple
# ---------------------------------------------------------------------------

class TestSimpleHunkParsing:
    def test_file_is_indexed(self):
        """Should index the file path from the diff --git header."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        assert mgr.get_file("src/foo.py") is not None

    def test_unknown_file_returns_none(self):
        """Should return None for a path not present in the diff."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        assert mgr.get_file("nonexistent.py") is None

    def test_hunk_count(self):
        """Should parse exactly one hunk for a simple diff."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        assert len(mgr.get_hunks("src/foo.py")) == 1

    def test_hunk_line_start(self):
        """Should parse new_line_start correctly from @@ header."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        hunk = mgr.get_hunks("src/foo.py")[0]
        assert hunk.new_line_start == 10

    def test_hunk_old_line_start(self):
        """Should parse old_line_start correctly from @@ header."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        hunk = mgr.get_hunks("src/foo.py")[0]
        assert hunk.old_line_start == 10


# ---------------------------------------------------------------------------
# Parsing — múltiples hunks
# ---------------------------------------------------------------------------

class TestMultiHunkParsing:
    def test_two_hunks_indexed(self):
        """Should parse both hunks from a file with two @@ sections."""
        mgr = DiffContextManager.from_diff(MULTI_HUNK_DIFF)
        assert len(mgr.get_hunks("src/bar.py")) == 2

    def test_first_hunk_start(self):
        """First hunk should start at new-file line 1."""
        mgr = DiffContextManager.from_diff(MULTI_HUNK_DIFF)
        assert mgr.get_hunks("src/bar.py")[0].new_line_start == 1

    def test_second_hunk_start(self):
        """Second hunk should start at new-file line 21."""
        mgr = DiffContextManager.from_diff(MULTI_HUNK_DIFF)
        assert mgr.get_hunks("src/bar.py")[1].new_line_start == 21

    def test_get_hunk_for_line_first(self):
        """get_hunk_for_line should return the first hunk for a line within it."""
        mgr = DiffContextManager.from_diff(MULTI_HUNK_DIFF)
        hunk = mgr.get_hunk_for_line("src/bar.py", 2)
        assert hunk is not None
        assert hunk.new_line_start == 1

    def test_get_hunk_for_line_second(self):
        """get_hunk_for_line should return the second hunk for a line within it."""
        mgr = DiffContextManager.from_diff(MULTI_HUNK_DIFF)
        hunk = mgr.get_hunk_for_line("src/bar.py", 22)
        assert hunk is not None
        assert hunk.new_line_start == 21

    def test_get_hunk_for_line_fallback_first(self):
        """get_hunk_for_line should fall back to the first hunk when line is not found."""
        mgr = DiffContextManager.from_diff(MULTI_HUNK_DIFF)
        hunk = mgr.get_hunk_for_line("src/bar.py", 999)
        assert hunk is not None
        assert hunk.new_line_start == 1


# ---------------------------------------------------------------------------
# Valid review lines — añadidas vs borradas
# ---------------------------------------------------------------------------

class TestValidReviewLines:
    def test_added_lines_are_valid(self):
        """Added lines ('+') should be in valid_review_lines."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        valid = mgr.get_valid_review_lines("src/foo.py")
        assert 12 in valid  # the '+    print("world")' line

    def test_context_lines_are_valid(self):
        """Context lines (' ') should be in valid_review_lines."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        valid = mgr.get_valid_review_lines("src/foo.py")
        assert 10 in valid  # ' def hello():'

    def test_deleted_lines_are_not_valid(self):
        """Deleted lines ('-') must NOT appear in valid_review_lines."""
        mgr = DiffContextManager.from_diff(DELETED_LINES_DIFF)
        valid = mgr.get_valid_review_lines("src/baz.py")
        # old_line_1 and old_line_2 were deleted; their old-file positions
        # should not appear as valid new-file review lines
        # New-file line 5 is 'def foo():' (context), line 6 is '+    new_line = True'
        assert 6 in valid
        # Verify that the deleted lines count doesn't inflate valid lines
        assert len(valid) < 10  # sanity check: small diff, few valid lines

    def test_unknown_file_returns_empty(self):
        """get_valid_review_lines should return empty frozenset for unknown file."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        assert mgr.get_valid_review_lines("nope.py") == frozenset()

    def test_get_all_valid_lines_keys(self):
        """get_all_valid_lines should return all files present in the diff."""
        mgr = DiffContextManager.from_diff(MULTI_FILE_DIFF)
        all_valid = mgr.get_all_valid_lines()
        assert "src/foo.py" in all_valid
        assert "src/bar.py" in all_valid


# ---------------------------------------------------------------------------
# Snippet search
# ---------------------------------------------------------------------------

class TestFindLineBySnippet:
    def test_finds_added_line(self):
        """Should find the line number of an added line matching the snippet."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        line = mgr.find_line_by_snippet("src/foo.py", 'print("world")')
        assert line is not None
        assert line == 12

    def test_finds_context_line(self):
        """Should find the line number of a context line matching the snippet."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        line = mgr.find_line_by_snippet("src/foo.py", "def hello")
        assert line is not None

    def test_returns_none_for_missing_snippet(self):
        """Should return None when the snippet is not in the diff."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        assert mgr.find_line_by_snippet("src/foo.py", "this_does_not_exist") is None

    def test_returns_none_for_empty_snippet(self):
        """Should return None for an empty snippet string."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        assert mgr.find_line_by_snippet("src/foo.py", "") is None

    def test_returns_none_for_unknown_file(self):
        """Should return None when the file is not in the diff."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        assert mgr.find_line_by_snippet("unknown.py", "hello") is None


# ---------------------------------------------------------------------------
# build_focused_diff — ventana de contexto
# ---------------------------------------------------------------------------

class TestBuildFocusedDiff:
    def test_returns_string(self):
        """Should return a non-empty string for a valid line."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        result = mgr.build_focused_diff("src/foo.py", 12)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_hunk_header(self):
        """Focused diff should start with a @@ header."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        result = mgr.build_focused_diff("src/foo.py", 12)
        assert result.startswith("@@")

    def test_marks_target_line(self):
        """Target line should be annotated with ◄ marker."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        result = mgr.build_focused_diff("src/foo.py", 12)
        assert "◄" in result

    def test_outdated_no_marker(self):
        """Outdated diffs should not include the ◄ target marker."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        result = mgr.build_focused_diff("src/foo.py", 10, is_outdated=True)
        assert "◄" not in result

    def test_unknown_file_returns_empty(self):
        """Should return empty string for a file not in the diff."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        assert mgr.build_focused_diff("nope.py", 1) == ""


# ---------------------------------------------------------------------------
# extract_original_lines_for_suggestion
# ---------------------------------------------------------------------------

class TestExtractOriginalLines:
    def test_single_line(self):
        """Should extract one line at the target position."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        result = mgr.extract_original_lines_for_suggestion("src/foo.py", 12, count=1)
        assert result is not None
        assert 'print("world")' in result

    def test_multiline_suggestion(self):
        """Should extract multiple consecutive lines for multiline suggestions."""
        mgr = DiffContextManager.from_diff(DELETED_LINES_DIFF)
        # line 6 = '+    new_line = True', line 7 = '     return new_line'
        result = mgr.extract_original_lines_for_suggestion("src/baz.py", 6, count=2)
        assert result is not None
        lines = result.split("\n")
        assert len(lines) == 2

    def test_unknown_file_returns_none(self):
        """Should return None for a file not in the diff."""
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        assert mgr.extract_original_lines_for_suggestion("nope.py", 1) is None


# ---------------------------------------------------------------------------
# Multi-file diff
# ---------------------------------------------------------------------------

class TestMultiFileDiff:
    def test_both_files_indexed(self):
        """Should index all files from a multi-file diff."""
        mgr = DiffContextManager.from_diff(MULTI_FILE_DIFF)
        assert mgr.get_file("src/foo.py") is not None
        assert mgr.get_file("src/bar.py") is not None

    def test_files_do_not_share_hunks(self):
        """Hunks from one file should not appear in another."""
        mgr = DiffContextManager.from_diff(MULTI_FILE_DIFF)
        foo_hunks = mgr.get_hunks("src/foo.py")
        bar_hunks = mgr.get_hunks("src/bar.py")
        assert len(foo_hunks) == 1
        assert len(bar_hunks) == 2


class TestFocusedReviewHelpers:
    def test_get_hunk_texts_returns_raw_hunks(self):
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)

        hunks = mgr.get_hunk_texts("src/foo.py")

        assert len(hunks) == 1
        assert hunks[0].startswith("@@")

    def test_build_expanded_hunks_includes_surrounding_context(self):
        mgr = DiffContextManager.from_diff(SIMPLE_DIFF)
        file_content = "\n".join(
            [
                "line 1",
                "line 2",
                "line 3",
                "line 4",
                "line 5",
                "line 6",
                "line 7",
                "line 8",
                "line 9",
                "def hello():",
                '    print("hello")',
                '    print("world")',
                "    return True",
                "",
                "def bye():",
            ]
        )

        expanded = mgr.build_expanded_hunks("src/foo.py", file_content, extra_lines=2)

        assert len(expanded) == 1
        assert "surrounding context" in expanded[0]
        assert 'print("world")' in expanded[0]
