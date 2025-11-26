# Guide: Creating a New Visual Component

This guide outlines the best practices and required steps for creating a new, theme-aware visual component for Titan CLI. Following this pattern ensures all UI components are consistent, maintainable, and testable.

## 1. File Structure

First, create the necessary files for your component and its preview.

1.  **Component File:** New components should live in `titan_cli/ui/components/`.
    -   Example: `titan_cli/ui/components/my_component.py`
2.  **Preview Script:** Create a corresponding preview script in `titan_cli/ui/components/__previews__/`.
    -   Example: `titan_cli/ui/components/__previews__/my_component_preview.py`

## 2. Component Implementation Principles

Your component should be a class (e.g., `MyComponentRenderer`) that follows these key principles:

-   **Class-based:** Encapsulates logic and state.
-   **Dependency Injection:** The `__init__` method must accept a `console: Optional[Console] = None` argument. It should default to using the global `get_console()` instance if none is provided. This is crucial for theme awareness and testability.
    ```python
    from rich.console import Console
    from ..console import get_console # Import the global console getter

    class MyComponentRenderer:
        def __init__(self, console: Optional[Console] = None):
            if console is None:
                console = get_console()
            self.console = console
    ```
-   **Use Theme Styles:** The component must use semantic style names defined in `titan_cli/ui/theme.py` (e.g., `"success"`, `"primary"`) instead of hardcoded colors like `"green"`.
-   **Use Centralized Messages:** All user-visible text (emojis, status messages) should be imported from `titan_cli.messages.msg`.

## 3. Example: `TableRenderer` Component (`titan_cli/ui/components/table.py`)

Here's how the `TableRenderer` component is implemented following the above principles:

```python
# titan_cli/ui/components/table.py

from typing import List, Optional, Literal, Union
from rich.table import Table
from rich.console import Console
from rich import box as rich_box
from ..console import get_console

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
    def __init__(self, console: Optional[Console] = None):
        if console is None:
            console = get_console()
        self.console = console

    def render(
        self,
        headers: List[str],
        rows: List[List[str]],
        title: Optional[str] = None,
        show_header: bool = True,
        show_lines: bool = False,
        box_style: BoxStyleOrBox = "rounded",
        title_style: Optional[str] = "primary",
        header_style: Optional[str] = "primary",
        row_styles: Optional[List[str]] = None,
        caption: Optional[str] = None,
        expand: bool = False
    ) -> Table:
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
        table = self.render(headers, rows, **kwargs)
        self.console.print(table)

    def _resolve_box_style(self, box_style: BoxStyleOrBox) -> Optional[rich_box.Box]:
        if box_style is None:
            return None
        if isinstance(box_style, rich_box.Box):
            return box_style
        if isinstance(box_style, str):
            return BOX_STYLES.get(box_style)
        return None
```

## 4. Example: `TableRenderer` Preview Script (`titan_cli/ui/components/__previews__/table_preview.py`)

Here's how the preview script for `TableRenderer` is implemented:

```python
# titan_cli/ui/components/__previews__/table_preview.py

from titan_cli.ui.components.table import TableRenderer
from titan_cli.ui.components.typography import TextRenderer

def preview_all():
    text = TextRenderer()
    renderer = TableRenderer()

    text.title("Table Component Preview")
    text.subtitle("A demonstration of the TableRenderer component.")
    text.line()

    text.title("1. Basic Table")
    headers = ["ID", "Name", "Status"]
    rows = [
        ["101", "Alice", "[green]Active[/green]"],
        ["102", "Bob", "[yellow]Pending[/yellow]"],
        ["103", "Charlie", "[red]Inactive[/red]"],
    ]
    renderer.print_table(headers=headers, rows=rows, title="User Status")
    text.line()

    text.success("Table Preview Complete")

if __name__ == "__main__":
    preview_all()
```

## 5. Add the Preview Command

Make your preview accessible via the CLI by adding a command to `titan_cli/preview.py`.

```python
# titan_cli/preview.py

# ... existing imports and commands ...

@preview_app.command("table")
def preview_table():
    """Shows a preview of the Table component."""
    try:
        runpy.run_module("titan_cli.ui.components.__previews__.table_preview", run_name="__main__")
    except ModuleNotFoundError:
        typer.secho("Error: Preview script not found.", fg=typer.colors.RED)
        raise typer.Exit(1)
```

## 6. Verify

Run your new preview command from the project root to see your component in action.

```bash
titan preview table
```

By following these steps, your new component will be perfectly integrated into the project's design system.