#!/usr/bin/env python3
"""
Preview for Status Bar Component

Usage:
    python -m titan_cli.ui.views.__previews__.status_bar_preview
"""

from pathlib import Path
import sys

# Add parent directory to path to import titan_cli modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from titan_cli.ui.views.status_bar import StatusBarRenderer
from titan_cli.ui.console import get_console
from titan_cli.core.config import TitanConfig


def preview_status_bar():
    """Preview the status bar with actual config."""
    console = get_console()

    console.print("\n[bold]Status Bar Preview[/bold]\n")

    # Preview 1: With config
    console.print("[yellow]1. Status Bar with config:[/yellow]")
    try:
        config = TitanConfig()
        info = config.get_status_bar_info()
        renderer = StatusBarRenderer(
            ai_info=info['ai_info'],
            project_name=info['project_name']
        )
        renderer.print()
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        console.print("\n[yellow]Showing status bar without config:[/yellow]")
        renderer = StatusBarRenderer()
        renderer.print()

    console.print("\n[yellow]2. Status Bar without config:[/yellow]")
    renderer_no_config = StatusBarRenderer()
    renderer_no_config.print()

    # Show how it looks in a menu context
    console.print("\n[yellow]3. Status Bar in menu context:[/yellow]")
    console.print("─" * console.width)
    console.print("\n[bold]Main Menu[/bold]")
    console.print("  1. Option 1")
    console.print("  2. Option 2")
    console.print("  3. Option 3")
    console.print("\n" + "─" * console.width)
    try:
        config = TitanConfig()
        info = config.get_status_bar_info()
        renderer = StatusBarRenderer(
            ai_info=info['ai_info'],
            project_name=info['project_name']
        )
        renderer.print()
    except Exception:
        renderer_no_config.print()
    console.print("─" * console.width + "\n")


if __name__ == "__main__":
    preview_status_bar()
