"""Tests for the Table widget's flexible-column sizing."""

from rich.text import Text

from titan_cli.ui.tui.widgets.table_layout import (
    MIN_FLEX_WIDTH,
    cell_width,
    compute_flex_width,
    wrap_cell,
)


HEADERS = ["#", "Issue", "Signals", "Events", "Users"]


def _rows(issue="HomeViewData"):
    return [["1", issue, "REPETITIVE", "115", "23"]]


class TestCellWidth:
    def test_plain_string(self):
        assert cell_width("abcd") == 4

    def test_longest_line_of_a_multiline_cell(self):
        assert cell_width("ab\nabcdef\nabc") == 6

    def test_rich_text_measured_without_its_markup(self):
        assert cell_width(Text("abcd", style="bold")) == 4

    def test_empty_cell(self):
        assert cell_width("") == 0


class TestComputeFlexWidth:
    def test_flex_column_takes_what_the_others_leave(self):
        # (1+2) + (10+2) + (6+2) + (5+2) for the fixed columns, + 2 padding for the flex one
        width = compute_flex_width(100, HEADERS, _rows(), flex_column=1)
        assert width == 100 - (3 + 12 + 8 + 7 + 2)

    def test_every_column_of_the_terminal_is_used(self):
        """Nothing is held back for a scrollbar: the widget is as tall as its content."""
        rows = _rows()
        flex = compute_flex_width(100, HEADERS, rows, flex_column=1)
        fixed = sum(max(len(h), cell_width(rows[0][i])) + 2 for i, h in enumerate(HEADERS) if i != 1)
        assert flex + 2 + fixed == 100

    def test_columns_are_sized_by_their_widest_cell_not_their_header(self):
        narrow = compute_flex_width(100, HEADERS, [["1", "x", "", "1", "1"]], flex_column=1)
        wide = compute_flex_width(100, HEADERS, [["1", "x", "REGRESSED · EARLY", "1", "1"]], flex_column=1)
        assert wide == narrow - len("REGRESSED · EARLY") + len("Signals")

    def test_long_flex_content_does_not_widen_the_column(self):
        """The whole point: the flexible column is sized by what is left, not by its content."""
        short = compute_flex_width(100, HEADERS, _rows("Home"), flex_column=1)
        long = compute_flex_width(100, HEADERS, _rows("Home" + "Nav" * 60), flex_column=1)
        assert short == long

    def test_never_narrower_than_the_minimum(self):
        assert compute_flex_width(20, HEADERS, _rows(), flex_column=1) == MIN_FLEX_WIDTH

    def test_single_column_table(self):
        assert compute_flex_width(40, ["Issue"], [["x"]], flex_column=0) == 40 - 2


class TestWrapCell:
    def test_short_text_stays_on_one_line(self):
        folded, lines = wrap_cell("HomeViewData", 40)
        assert folded.plain == "HomeViewData"
        assert lines == 1

    def test_text_longer_than_the_column_is_folded(self):
        folded, lines = wrap_cell("one two three four five six", 10)
        assert lines > 1
        assert all(len(line) <= 10 for line in folded.plain.split("\n"))

    def test_a_word_longer_than_the_column_is_broken(self):
        """Class and method names have no spaces to break on."""
        folded, lines = wrap_cell("A" * 30, 10)
        assert lines == 3
        assert folded.plain.split("\n") == ["A" * 10] * 3

    def test_existing_newlines_are_kept(self):
        folded, lines = wrap_cell(Text("title\nsubtitle"), 40)
        assert folded.plain == "title\nsubtitle"
        assert lines == 2

    def test_styles_survive_the_fold(self):
        cell = Text("title", style="bold")
        cell.append("\na rather long subtitle that wraps", style="dim")
        folded, _ = wrap_cell(cell, 12)
        styles = {str(span.style) for span in folded.spans}
        assert "bold" in styles
        assert "dim" in styles

    def test_zero_width_returns_the_cell_untouched(self):
        folded, lines = wrap_cell("anything", 0)
        assert folded.plain == "anything"
        assert lines == 1

    def test_empty_cell(self):
        folded, lines = wrap_cell("", 20)
        assert folded.plain == ""
        assert lines == 1
