"""The diff widget's drawing, as a pure function: text, numbers, tint and the line cap."""
from types import SimpleNamespace as NS

from titan_cli.ui.elements import DIFF_COMPONENT, Component, Diff, DiffProps
from titan_cli.ui.tui.widgets.diff_view import DiffView, layout_diff, render_diff
from titan_cli.ui.tui.widgets.element_widgets import kind


def _line(kind_, text, old=None, new=None):
    return NS(kind=kind_, text=text, old_no=old, new_no=new)


def _diff(*hunks, path="a.py", is_binary=False):
    return NS(path=path, is_binary=is_binary, hunks=list(hunks))


MODIFIED = _diff(
    NS(
        header="@@ -1,3 +1,3 @@",
        lines=[
            _line("context", "keep", 1, 1),
            _line("del", "old = 1", 2, None),
            _line("add", "new = 2", None, 2),
            _line("no_newline", "No newline at end of file"),
        ],
    )
)


def _rows(diff, width=40, max_lines=400):
    return render_diff(diff, width, max_lines).plain.split("\n")


def _bg_at(diff, row, width=40):
    """The backgrounds the spans give row `row`, over the row's own characters only."""
    text = render_diff(diff, width, 400)
    rows = text.plain.split("\n")
    start = sum(len(r) + 1 for r in rows[:row])
    end = start + len(rows[row])
    return {str(s.style.bgcolor) for s in text.spans if s.style.bgcolor and s.start < end and s.end > start}


def test_rows_have_header_numbers_marker_and_code():
    rows = _rows(MODIFIED)

    assert rows[0].strip() == "@@ -1,3 +1,3 @@"
    assert rows[1].startswith("  1 1   keep")
    assert rows[2].startswith("▌ 2   - old = 1")
    assert rows[3].startswith("▌   2 + new = 2")
    assert "\\ No newline at end of file" in rows[4]


def test_tinted_lines_fill_the_whole_width_and_context_does_not():
    assert all(len(r) == 40 for r in (_rows(MODIFIED)[2], _rows(MODIFIED)[3]))
    assert _bg_at(MODIFIED, 2) and _bg_at(MODIFIED, 3) and not _bg_at(MODIFIED, 1)
    assert _bg_at(MODIFIED, 2) != _bg_at(MODIFIED, 3)


def test_a_file_that_is_all_additions_has_one_number_column():
    new_file = _diff(NS(header="@@ -0,0 +1,2 @@", lines=[_line("add", "a", None, 1), _line("add", "b", None, 2)]))

    rows = _rows(new_file)

    assert rows[1].startswith("▌ 1 + a")
    assert rows[2].startswith("▌ 2 + b")


def test_gutter_widens_with_the_largest_line_number():
    far = _diff(NS(header="@@ -99,1 +99,1 @@", lines=[_line("context", "x", 99, 99), _line("add", "y", None, 100)]))

    assert _rows(far)[1].startswith("   99  99   x")


def test_a_long_line_is_not_cut_and_the_tint_reaches_its_end():
    long = _diff(NS(header="@@", lines=[_line("add", "x" * 200, None, 1), _line("add", "y", None, 2)]))

    rows = _rows(long, width=30)

    assert "x" * 200 in rows[1]
    assert len(rows[1]) == len(rows[2]) > 200


def test_layout_reports_the_width_the_scrolling_box_needs():
    long = _diff(NS(header="@@", lines=[_line("add", "x" * 200, None, 1)]))

    assert layout_diff(long, 30, 400)[1] > 200
    assert layout_diff(MODIFIED, 40, 400)[1] == 40
    assert layout_diff(_diff(is_binary=True), 40, 400)[1] == 0


def test_tabs_become_spaces():
    tabbed = _diff(NS(header="@@", lines=[_line("add", "\treturn 1", None, 1)]))

    assert "\t" not in render_diff(tabbed, 40, 400).plain


def test_past_max_lines_it_says_how_many_more():
    many = _diff(NS(header="@@", lines=[_line("add", f"l{i}", None, i + 1) for i in range(10)]))

    rows = _rows(many, max_lines=4)

    assert [r for r in rows if "l3" in r] and not [r for r in rows if "l4" in r]
    assert rows[-1].strip() == "… 6 more lines"


def test_binary_and_empty_diffs_say_so():
    assert _rows(_diff(is_binary=True)) == ["Binary file not shown"]
    assert _rows(_diff()) == ["No changes to show"]


def test_unknown_extension_still_draws_plain_code():
    odd = _diff(NS(header="@@", lines=[_line("add", "hello", None, 1)]), path="notes.zzzz")

    assert "+ hello" in _rows(odd)[1]


def test_syntax_colours_are_kept_but_the_background_is_the_lines():
    code = _diff(NS(header="@@", lines=[_line("add", "def f(): return 1", None, 1), _line("add", "x = 2", None, 2)]))

    text = render_diff(code, 40, 400)

    rows = text.plain.split("\n")
    keyword = len(rows[0]) + 1 + rows[1].index("def")  # spans index the whole text
    colours = {str(s.style.color.name) for s in text.spans if s.style.color and s.start <= keyword + 1 < s.end}
    assert "#ff79c6" in colours  # `def` is a keyword
    backgrounds = {str(s.style.bgcolor.name) for s in text.spans if s.style.bgcolor}
    assert backgrounds == {"#343746", "#16301f"}  # the hunk header's and the added lines', nothing from the theme


def test_the_element_names_the_registered_widget():
    element = Diff(MODIFIED, max_lines=50)

    assert element == Component(DIFF_COMPONENT, DiffProps(MODIFIED, 50))
    assert kind(element) is DiffView
