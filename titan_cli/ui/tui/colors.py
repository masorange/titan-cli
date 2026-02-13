"""
Titan TUI Color Palette

Centralized color definitions for the Textual UI using Dracula theme.
These colors are used both in CSS variables (theme.py) and in Python code
(for Rich Text objects that can't use CSS).

This ensures consistency across the entire application and allows easy theme changes.
"""

# Dracula Color Palette
# Source: https://draculatheme.com/contribute

# Primary Colors
PRIMARY = "#bd93f9"      # Purple (Dracula standard)
SECONDARY = "#50fa7b"    # Green
ACCENT = "#ff79c6"       # Pink

# Semantic Colors
ERROR = "#ff5555"        # Red
WARNING = "#f1fa8c"      # Yellow
SUCCESS = "#50fa7b"      # Green
INFO = "#8be9fd"         # Cyan

# Background Colors
SURFACE = "#282a36"           # Dark background
SURFACE_LIGHTEN_1 = "#343746" # Slightly lighter
SURFACE_LIGHTEN_2 = "#44475a" # Comment color

# Text Colors
TEXT = "#f8f8f2"              # Foreground (almost white)
TEXT_MUTED = "#6272a4"        # Comment/dim text
TEXT_DISABLED = "#44475a"     # Disabled state

# Additional Dracula Colors
ORANGE = "#ffb86c"       # Orange
CYAN = "#8be9fd"         # Cyan
PINK = "#ff79c6"         # Pink
YELLOW = "#f1fa8c"       # Yellow
GREEN = "#50fa7b"        # Green
RED = "#ff5555"          # Red
PURPLE = "#bd93f9"       # Purple


# Rich Style Strings
# These can be used directly with Rich Text objects
# Format: "color" or "style color" or "style1 style2 color"

class RichStyles:
    """Rich-compatible style strings using theme colors."""

    # Basic colors
    PRIMARY = PRIMARY
    SUCCESS = SUCCESS
    ERROR = ERROR
    WARNING = WARNING
    INFO = INFO

    # Text colors
    TEXT = TEXT
    DIM = TEXT_MUTED
    MUTED = TEXT_MUTED

    # Combined styles (for Rich Text)
    BOLD_PRIMARY = f"bold {PRIMARY}"
    BOLD_SUCCESS = f"bold {SUCCESS}"
    BOLD_ERROR = f"bold {ERROR}"
    BOLD_WARNING = f"bold {WARNING}"

    DIM_PRIMARY = f"dim {PRIMARY}"
    DIM_SUCCESS = f"dim {SUCCESS}"
    DIM_ERROR = f"dim {ERROR}"
    DIM_WARNING = f"dim {WARNING}"

    # For diff/code rendering
    # Green for additions
    ADD = SUCCESS
    ADD_DIM = f"dim {SUCCESS}"
    ADD_BOLD = f"bold {SUCCESS}"

    # Red for deletions
    REMOVE = ERROR
    REMOVE_DIM = f"dim {ERROR}"
    REMOVE_BOLD = f"bold {ERROR}"

    # Purple for context/info
    CONTEXT = TEXT_MUTED
    CONTEXT_DIM = f"dim {TEXT_MUTED}"


# Convenience function to get Rich color from semantic name
def get_rich_color(semantic_name: str) -> str:
    """
    Get a Rich-compatible color string from a semantic name.

    Args:
        semantic_name: Color name like "primary", "success", "error", etc.

    Returns:
        Hex color string

    Examples:
        >>> get_rich_color("success")
        '#50fa7b'
        >>> get_rich_color("error")
        '#ff5555'
    """
    colors = {
        "primary": PRIMARY,
        "secondary": SECONDARY,
        "accent": ACCENT,
        "success": SUCCESS,
        "error": ERROR,
        "warning": WARNING,
        "info": INFO,
        "text": TEXT,
        "muted": TEXT_MUTED,
        "dim": TEXT_MUTED,
        "disabled": TEXT_DISABLED,
    }
    return colors.get(semantic_name.lower(), TEXT)


# Export all
__all__ = [
    # Colors
    "PRIMARY",
    "SECONDARY",
    "ACCENT",
    "ERROR",
    "WARNING",
    "SUCCESS",
    "INFO",
    "SURFACE",
    "SURFACE_LIGHTEN_1",
    "SURFACE_LIGHTEN_2",
    "TEXT",
    "TEXT_MUTED",
    "TEXT_DISABLED",
    "ORANGE",
    "CYAN",
    "PINK",
    "YELLOW",
    "GREEN",
    "RED",
    "PURPLE",
    # Rich Styles
    "RichStyles",
    # Helper
    "get_rich_color",
]
