"""
Table Widget

A simple table widget for displaying tabular data.
"""

from typing import List, Literal
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable


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

        # Add columns
        for header in self.headers:
            table.add_column(header)

        # Add rows
        for row in self.rows:
            table.add_row(*row, height=self.row_height)

        yield table
