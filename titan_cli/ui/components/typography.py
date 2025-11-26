"""
Text Component

Reusable wrapper for rich.console.print with theme-aware styling.

Provides consistent text rendering with:
- Theme-aware color schemes
- Predefined styles (title, subtitle, success, error, etc.)
- Centralized configuration
- Dependency injection support

This follows the same pattern as PanelRenderer for consistency.

Examples:
    >>> # Basic usage
    >>> renderer = TextRenderer()  # Uses global theme-aware console
    >>> renderer.title("Main Title")
    >>> renderer.success("Operation completed!")

    >>> # Custom console (for testing)
    >>> custom_console = Console(file=StringIO())
    >>> renderer = TextRenderer(console=custom_console)
"""

from typing import Optional, Literal
from rich.console import Console
from ..console import get_console
from ...messages import msg


class TextRenderer:
    """
    Reusable wrapper for text rendering with theme-aware styling

    Follows the same pattern as PanelRenderer for consistency.
    """

    def __init__(
        self,
        console: Optional[Console] = None,
        show_emoji: bool = True
    ):
        """
        Initialize text renderer

        Args:
            console: Rich Console instance (uses global theme-aware console if None)
            show_emoji: Show emoji prefixes in status messages by default
        """
        if console is None:
            console = get_console()
        self.console = console
        self.default_show_emoji = show_emoji

    def title(self, text: str, justify: Literal["left", "center", "right"] = "left") -> None:
        """Print a main title with bold primary styling"""
        self.console.print(f"[bold primary]{text}[/bold primary]", justify=justify)

    def subtitle(self, text: str, justify: Literal["left", "center", "right"] = "left") -> None:
        """Print a subtitle with dimmed styling"""
        self.console.print(f"[dim]{text}[/dim]", justify=justify)

    def body(self, text: str, style: Optional[str] = None) -> None:
        """Print standard body text"""
        if style:
            self.console.print(f"[{style}]{text}[/{style}]")
        else:
            self.console.print(text)

    def success(self, text: str, show_emoji: Optional[bool] = None, justify: Literal["left", "center", "right"] = "left") -> None:
        """Print a success message with green styling"""
        if show_emoji is None:
            show_emoji = self.default_show_emoji
        prefix = f"{msg.EMOJI.SUCCESS} " if show_emoji else ""
        self.console.print(f"{prefix}{text}", style="success", justify=justify)

    def error(self, text: str, show_emoji: Optional[bool] = None, justify: Literal["left", "center", "right"] = "left") -> None:
        """Print an error message with red styling"""
        if show_emoji is None:
            show_emoji = self.default_show_emoji
        prefix = f"{msg.EMOJI.ERROR} " if show_emoji else ""
        self.console.print(f"{prefix}{text}", style="error", justify=justify)

    def warning(self, text: str, show_emoji: Optional[bool] = None, justify: Literal["left", "center", "right"] = "left") -> None:
        """Print a warning message with yellow styling"""
        if show_emoji is None:
            show_emoji = self.default_show_emoji
        prefix = f"{msg.EMOJI.WARNING} " if show_emoji else ""
        self.console.print(f"{prefix}{text}", style="warning", justify=justify)

    def info(self, text: str, show_emoji: Optional[bool] = None, justify: Literal["left", "center", "right"] = "left") -> None:
        """Print an informational message with cyan styling"""
        if show_emoji is None:
            show_emoji = self.default_show_emoji
        prefix = f"{msg.EMOJI.INFO} " if show_emoji else ""
        self.console.print(f"{prefix}{text}", style="info", justify=justify)

    def line(self, count: int = 1) -> None:
        """Print blank lines for spacing"""
        for _ in range(count):
            self.console.print()

    def divider(self, char: str = "─", style: Optional[str] = "dim") -> None:
        """Print a horizontal divider line"""
        divider_line = char * self.console.width
        if style:
            self.console.print(f"[{style}]{divider_line}[/{style}]")
        else:
            self.console.print(divider_line)