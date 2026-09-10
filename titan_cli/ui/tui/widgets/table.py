"""
Table Widget

A simple table widget for displaying tabular data.
"""

from typing import List, Literal, Optional
from textual.app import ComposeResult
from textual.events import Resize
from textual.widget import Widget
from textual.widgets import DataTable

from titan_cli.ui.tui.widgets.table_layout import compute_flex_width, wrap_cell


CursorType = Literal["cell", "row", "column", "none"]


class Table(Widget):
    """Table widget for displaying rows and columns."""

    DEFAULT_CSS = """
    Table {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
    }

    Table.compact {
        width: auto;
    }

    Table > DataTable {
        width: 100%;
        height: auto;
    }

    Table.compact > DataTable {
        width: auto;
    }
    """

    def __init__(
        self,
        headers: List[str],
        rows: List[List[str]],
        title: str = "",
        full_width: bool = True,
        cell_padding: int = 1,
        zebra_stripes: bool = False,
        show_header: bool = True,
        show_cursor: bool = True,
        cursor_type: CursorType = "row",
        row_height: int = 1,
        flex_column: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize table.

        Args:
            headers: List of column headers
            rows: List of rows (each row is a list of cell values)
            title: Optional title for the table
            full_width: If False, table uses auto width (compact mode)
            cell_padding: Horizontal padding inside each cell (default 1)
            zebra_stripes: Alternate row background colours
            show_header: Show the column header row
            show_cursor: Show the cursor highlight
            cursor_type: Cursor movement mode ("cell", "row", "column", "none")
            row_height: Number of lines per row (default 1, use 2+ for multiline cells)
            flex_column: Index of the column that absorbs the leftover width. Its text is
                folded into that width and rows grow as tall as they need, so the columns
                after it stay on screen instead of requiring a horizontal scroll.
        """
        super().__init__(**kwargs)
        self.headers = headers
        self.rows = rows
        self.title_text = title
        self.cell_padding = cell_padding
        self.zebra_stripes = zebra_stripes
        self.show_header = show_header
        self.show_cursor = show_cursor
        self.cursor_type = cursor_type
        self.row_height = row_height
        self.flex_column = flex_column
        self._laid_out_width: Optional[int] = None

        # Add compact class if not full width
        if not full_width:
            self.add_class("compact")

    def compose(self) -> ComposeResult:
        """Compose the table."""
        table = DataTable(
            cell_padding=self.cell_padding,
            zebra_stripes=self.zebra_stripes,
            show_header=self.show_header,
            show_cursor=self.show_cursor,
            cursor_type=self.cursor_type,
        )
        if self.title_text:
            table.border_title = self.title_text

        # With a flexible column both the columns and the rows depend on the width, which
        # is unknown until the first layout; on_resize builds them and rebuilds on change.
        if self.flex_column is None:
            for header in self.headers:
                table.add_column(header)
            for row in self.rows:
                table.add_row(*row, height=self.row_height)

        yield table

    def on_resize(self, event: Resize) -> None:
        """Refold the flexible column when the available width changes."""
        if self.flex_column is None:
            return
        self._fill_rows(event.size.width)

    def _fill_rows(self, total_width: int) -> None:
        """(Re)build the rows with the flexible column folded into the width left for it."""
        flex_width = compute_flex_width(
            total_width, self.headers, self.rows, self.flex_column, self.cell_padding
        )
        if flex_width == self._laid_out_width:
            return
        self._laid_out_width = flex_width

        table = self.query_one(DataTable)
        table.clear(columns=True)
        # The flexible column is given the width explicitly. Left to size itself it
        # shrinks to its longest folded line, and the slack is dead space on the right.
        for index, header in enumerate(self.headers):
            table.add_column(header, width=flex_width if index == self.flex_column else None)
        for row in self.rows:
            cells = list(row)
            folded, lines = wrap_cell(cells[self.flex_column], flex_width)
            cells[self.flex_column] = folded
            # A blank line under a wrapped cell keeps rows apart; single-line rows
            # need no separator.
            height = max(lines + 1 if lines > 1 else 1, self.row_height)
            table.add_row(*cells, height=height)
