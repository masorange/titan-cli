"""
Column sizing for the Table widget.

Textual's DataTable sizes every column to its widest cell, so one long cell
(a stack-trace-shaped issue title, a file path) pushes the columns after it off
screen and the reader has to scroll sideways to see the numbers. Giving that
column a fixed width does not help either: DataTable crops the content to the
column, without an ellipsis and without using the extra lines of a tall row.

So the caller names one column as flexible, and these helpers give it whatever
width the other columns leave and fold its text into that width by hand. Pure
functions, so the arithmetic can be tested without a running app.
"""

from rich.console import Console
from rich.text import Text

# A flexible column narrower than this is unreadable; better to overflow.
MIN_FLEX_WIDTH = 24

_MEASURE_CONSOLE = Console(width=200, no_color=True)


def cell_width(value) -> int:
    """Width the terminal needs for a cell, i.e. its longest line."""
    plain = value.plain if isinstance(value, Text) else str(value)
    return max((len(line) for line in plain.split("\n")), default=0)


def compute_flex_width(
    total_width: int,
    headers: list[str],
    rows: list[list],
    flex_column: int,
    cell_padding: int = 1,
    minimum: int = MIN_FLEX_WIDTH,
) -> int:
    """Width left for the flexible column once every other column has what it needs.

    ``total_width`` is the space the table itself occupies, and all of it is usable:
    the widget grows to its content height (see ``Table``'s CSS), so DataTable never
    draws a vertical scrollbar that would need a gutter.
    """
    padding = 2 * cell_padding
    spent = 0
    for index, header in enumerate(headers):
        if index == flex_column:
            spent += padding
            continue
        widest = max([len(header)] + [cell_width(row[index]) for row in rows if index < len(row)])
        spent += widest + padding
    return max(total_width - spent, minimum)


def wrap_cell(value, width: int) -> tuple[Text, int]:
    """Fold a cell into ``width`` columns, keeping its styles, and say how many lines it took.

    Existing newlines are honoured, so a two-line "title + subtitle" cell stays
    two blocks. Words longer than the column are broken rather than cropped —
    class and method names have no spaces to break on.
    """
    text = value if isinstance(value, Text) else Text(str(value))
    if width <= 0:
        return text, 1
    lines = text.wrap(_MEASURE_CONSOLE, width, overflow="fold")
    if not lines:
        return text, 1
    return Text("\n").join(lines), len(lines)
