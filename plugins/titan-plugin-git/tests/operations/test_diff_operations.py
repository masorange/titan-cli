"""
Tests for Diff Operations

Tests for pure business logic related to diff parsing and formatting.
"""

from titan_plugin_git.operations.diff_operations import (
    parse_diff_stat_output,
    get_max_filename_length,
    colorize_diff_stats,
    colorize_diff_summary,
    format_diff_stat_display,
)


class TestParseDiffStatOutput:
    """Tests for parse_diff_stat_output function."""

    def test_parse_single_file(self):
        """Should parse single file with stats."""
        output = " file.py | 5 ++---"
        files, summary = parse_diff_stat_output(output)
        assert files == [("file.py", " 5 ++---")]
        assert summary == []

    def test_parse_multiple_files(self):
        """Should parse multiple files."""
        output = " file1.py | 3 +++\n file2.py | 2 --"
        files, summary = parse_diff_stat_output(output)
        assert len(files) == 2
        assert files[0] == ("file1.py", " 3 +++")
        assert files[1] == ("file2.py", " 2 --")

    def test_parse_with_summary(self):
        """Should parse files and summary separately."""
        output = " file.py | 5 ++---\n 1 file changed, 2 insertions(+), 3 deletions(-)"
        files, summary = parse_diff_stat_output(output)
        assert files == [("file.py", " 5 ++---")]
        assert summary == [" 1 file changed, 2 insertions(+), 3 deletions(-)"]

    def test_parse_empty_string(self):
        """Should handle empty input."""
        files, summary = parse_diff_stat_output("")
        assert files == []
        assert summary == []

    def test_parse_with_empty_lines(self):
        """Should skip empty lines."""
        output = " file.py | 5 ++---\n\n\n 1 file changed"
        files, summary = parse_diff_stat_output(output)
        assert len(files) == 1
        assert len(summary) == 1

    def test_parse_complex_filenames(self):
        """Should handle complex file paths."""
        output = " src/components/Button.tsx | 10 ++++++++++\n tests/unit/button.test.ts | 5 +++++"
        files, summary = parse_diff_stat_output(output)
        assert files[0][0] == "src/components/Button.tsx"
        assert files[1][0] == "tests/unit/button.test.ts"


class TestGetMaxFilenameLength:
    """Tests for get_max_filename_length function."""

    def test_single_file(self):
        """Should return length of single filename."""
        files = [("file.py", "")]
        assert get_max_filename_length(files) == 7

    def test_multiple_files(self):
        """Should return maximum length."""
        files = [("short.py", ""), ("very_long_filename.py", ""), ("mid.py", "")]
        assert get_max_filename_length(files) == 21  # len("very_long_filename.py")

    def test_empty_list(self):
        """Should return 0 for empty list."""
        assert get_max_filename_length([]) == 0

    def test_all_same_length(self):
        """Should handle all same length."""
        files = [("file1.py", ""), ("file2.py", ""), ("file3.py", "")]
        assert get_max_filename_length(files) == 8


class TestColorizeDiffStats:
    """Tests for colorize_diff_stats function."""

    def test_colorize_additions(self):
        """Should colorize + symbols."""
        result = colorize_diff_stats(" 5 +++")
        assert result == " 5 [green]+[/green][green]+[/green][green]+[/green]"

    def test_colorize_deletions(self):
        """Should colorize - symbols."""
        result = colorize_diff_stats(" 3 ---")
        assert result == " 3 [red]-[/red][red]-[/red][red]-[/red]"

    def test_colorize_mixed(self):
        """Should colorize both + and -."""
        result = colorize_diff_stats(" 5 ++---")
        assert "[green]+[/green]" in result
        assert "[red]-[/red]" in result

    def test_no_symbols(self):
        """Should handle text without symbols."""
        result = colorize_diff_stats(" 10 changes")
        assert result == " 10 changes"

    def test_empty_string(self):
        """Should handle empty string."""
        result = colorize_diff_stats("")
        assert result == ""


class TestColorizeDiffSummary:
    """Tests for colorize_diff_summary function."""

    def test_colorize_insertions(self):
        """Should colorize (+) marker."""
        result = colorize_diff_summary("10 insertions(+)")
        assert result == "10 insertions[green](+)[/green]"

    def test_colorize_deletions(self):
        """Should colorize (-) marker."""
        result = colorize_diff_summary("5 deletions(-)")
        assert result == "5 deletions[red](-)[/red]"

    def test_colorize_both(self):
        """Should colorize both markers."""
        result = colorize_diff_summary("3 files changed, 10 insertions(+), 5 deletions(-)")
        assert "[green](+)[/green]" in result
        assert "[red](-)[/red]" in result
        assert "3 files changed" in result

    def test_no_markers(self):
        """Should handle text without markers."""
        result = colorize_diff_summary("1 file changed")
        assert result == "1 file changed"


class TestFormatDiffStatDisplay:
    """Tests for format_diff_stat_display function."""

    def test_format_single_file(self):
        """Should format single file with colors and alignment."""
        output = " file.py | 5 ++---"
        files, summary = format_diff_stat_display(output)
        assert len(files) == 1
        assert "file.py" in files[0]
        assert "[green]+[/green]" in files[0]
        assert "[red]-[/red]" in files[0]

    def test_format_with_alignment(self):
        """Should align filenames."""
        output = " a.py | 1 +\n very_long_file.py | 2 ++"
        files, summary = format_diff_stat_display(output)
        # Both lines should have the same position for the pipe
        assert "a.py" in files[0]
        assert "very_long_file.py" in files[1]
        # First file should be padded
        assert len(files[0].split("|")[0]) == len(files[1].split("|")[0])

    def test_format_with_summary(self):
        """Should format summary lines with colors."""
        output = " file.py | 1 +\n 1 file changed, 1 insertion(+)"
        files, summary = format_diff_stat_display(output)
        assert len(files) == 1
        assert len(summary) == 1
        assert "[green](+)[/green]" in summary[0]

    def test_format_empty_output(self):
        """Should handle empty output."""
        files, summary = format_diff_stat_display("")
        assert files == []
        assert summary == []

    def test_format_real_git_output(self):
        """Should handle realistic git diff --stat output."""
        output = """plugins/titan-plugin-git/operations/diff.py     | 45 ++++++++++++++++++
 plugins/titan-plugin-git/operations/commit.py  | 32 ++++++++++++
 2 files changed, 77 insertions(+)"""
        files, summary = format_diff_stat_display(output)
        assert len(files) == 2
        assert len(summary) == 1
        assert "diff.py" in files[0]
        assert "commit.py" in files[1]
        assert "77 insertions" in summary[0]
