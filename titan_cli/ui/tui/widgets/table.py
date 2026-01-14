"""
Table Widget

A simple table widget for displaying tabular data.
"""

from typing import List
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable


class Table(Widget):
    """Table widget for displaying rows and columns."""

    DEFAULT_CSS = """
    Table {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
    }

    Table > DataTable {
        width: 100%;
        height: auto;
    }
    """

    def __init__(
        self,
        headers: List[str],
        rows: List[List[str]],
        title: str = "",
        **kwargs
    ):
        """
        Initialize table.

        Args:
            headers: List of column headers
            rows: List of rows (each row is a list of cell values)
            title: Optional title for the table
        """
        super().__init__(**kwargs)
        self.headers = headers
        self.rows = rows
        self.title_text = title

    def compose(self) -> ComposeResult:
        """Compose the table."""
        table = DataTable()
        if self.title_text:
            table.border_title = self.title_text

        # Add columns
        for header in self.headers:
            table.add_column(header)

        # Add rows
        for row in self.rows:
            table.add_row(*row)

        yield table
