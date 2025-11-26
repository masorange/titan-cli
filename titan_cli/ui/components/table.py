"""
Table Renderer Component

Reusable wrapper for rich.table.Table with centralized theme-aware styling.
"""

from typing import List, Optional, Literal, Union
from rich.table import Table
from rich.console import Console
from rich import box as rich_box
from ..console import get_console # Import our theme-aware console

BoxStyle = Literal["simple", "minimal", "rounded", "heavy", "double", "none"]
BoxStyleOrBox = Union[BoxStyle, rich_box.Box, None]

# Map box style names to Rich box types
BOX_STYLES = {
    "simple": rich_box.SIMPLE,
    "minimal": rich_box.MINIMAL,
    "rounded": rich_box.ROUNDED,
    "heavy": rich_box.HEAVY,
    "double": rich_box.DOUBLE,
    "none": None
}


class TableRenderer:
    """
    Reusable wrapper for rich.Table with theme-aware styling
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize TableRenderer

        Args:
            console: Optional Rich console. Uses the global theme-aware console if None.
        """
        if console is None:
            console = get_console() # Use our global theme-aware console
        self.console = console

    def render(
        self,
        headers: List[str],
        rows: List[List[str]],
        title: Optional[str] = None,
        show_header: bool = True,
        show_lines: bool = False,
        box_style: BoxStyleOrBox = "rounded",
        title_style: Optional[str] = "primary", # Use theme style
        header_style: Optional[str] = "primary", # Use theme style
        row_styles: Optional[List[str]] = None,
        caption: Optional[str] = None,
        expand: bool = False
    ) -> Table:
        """
        Render a table using Rich
        """
        box = self._resolve_box_style(box_style)

        table = Table(
            title=title,
            title_style=title_style,
            show_header=show_header,
            header_style=header_style,
            show_lines=show_lines,
            box=box,
            caption=caption,
            expand=expand
        )

        for header in headers:
            table.add_column(header)

        for i, row in enumerate(rows):
            style = None
            if row_styles:
                style = row_styles[i % len(row_styles)]
            table.add_row(*row, style=style)

        return table

    def print_table(
        self,
        headers: List[str],
        rows: List[List[str]],
        **kwargs
    ) -> None:
        """
        Render and print table in one step
        """
        table = self.render(headers, rows, **kwargs)
        self.console.print(table)

    def _resolve_box_style(self, box_style: BoxStyleOrBox) -> Optional[rich_box.Box]:
        """
        Resolve box style from string name or Box object
        """
        if box_style is None:
            return None
        if isinstance(box_style, rich_box.Box):
            return box_style
        if isinstance(box_style, str):
            return BOX_STYLES.get(box_style)
        return None
