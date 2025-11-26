"""
Typography Component Preview

Run this script to preview all typography variations:
    poetry run python -m titan_cli.ui.components.__previews__.typography_preview

This demonstrates the centralized text styling.
"""

from titan_cli.ui.components import typography
from titan_cli.ui.console import get_console
from titan_cli.messages import msg


def preview_all():
    """Preview all typography variations"""
    console = get_console()

    typography.title("Typography Component Preview")
    typography.subtitle("Showcasing all text styles from the typography module.")
    typography.line(2)

    # Title and Subtitle
    typography.title("1. Titles & Subtitles")
    typography.body("Using typography.title() and typography.subtitle():")
    typography.line()
    typography.title("Main Application Title", centered=True)
    typography.subtitle("A centered subtitle for context.", centered=True)
    typography.line()

    # Body Text
    typography.title("2. Body Text")
    typography.body("Standard body text using typography.body():")
    typography.line()
    typography.body("This is a piece of standard body text. It should appear without any special styling unless inherited from the console's default.")
    typography.body(f"You can also include variables like the current version: {msg.CLI.VERSION.format(version='0.1.0')}")
    typography.line()

    # Semantic Messages with Emojis
    typography.title("3. Semantic Messages (with Emojis)")
    typography.body("Messages with default emojis using typography.success(), error(), etc.:")
    typography.line()
    typography.success("Operation completed successfully.")
    typography.info("This is an important piece of information.")
    typography.warning("Something might be wrong here, proceed with caution.")
    typography.error("An unrecoverable error has occurred.")
    typography.line()

    # Semantic Messages without Emojis
    typography.title("4. Semantic Messages (without Emojis)")
    typography.body("Messages with emojis disabled using show_emoji=False:")
    typography.line()
    typography.success("Configuration loaded", show_emoji=False)
    typography.info("Checking dependencies", show_emoji=False)
    typography.warning("Disk space low", show_emoji=False)
    typography.error("Build failed", show_emoji=False)
    typography.line()

    # Line breaks
    typography.title("5. Line Breaks")
    typography.body("Using typography.line(count):")
    typography.body("Line above this.")
    typography.line(3)
    typography.body("Line below this (after 3 blank lines).")
    typography.line()

    typography.success("Typography Preview Complete")
    typography.line()


if __name__ == "__main__":
    preview_all()
