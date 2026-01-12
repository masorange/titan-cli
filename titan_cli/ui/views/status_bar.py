"""
Status Bar Component (View)

Visual component that displays project status information in 3 columns:
- Left: Git branch
- Center: AI provider and model
- Right: Active project

This is a view component because it composes multiple UI elements.
"""

import subprocess
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from ..console import get_console


class StatusBarRenderer:
    """
    Renders a status bar showing git branch, AI config, and active project.

    The status bar is designed to be displayed at the bottom of menus and
    provide quick context about the current environment.
    """

    def __init__(
        self,
        console: Optional[Console] = None,
        ai_info: Optional[str] = None,
        project_name: Optional[str] = None,
        branch: Optional[str] = None,
        auto_detect: bool = True
    ):
        """
        Initialize the StatusBarRenderer.

        Args:
            console: A Rich Console instance. If None, uses the global theme-aware console.
            ai_info: AI provider/model info (e.g., "anthropic/claude-3"). If None and auto_detect is True, shows "N/A".
            project_name: Project name to display. If None and auto_detect is True, uses current directory name.
            branch: Git branch name. If None and auto_detect is True, detects from git.
            auto_detect: If True, auto-detects missing values (git branch, project name).
        """
        if console is None:
            console = get_console()
        self.console = console
        self._ai_info = ai_info
        self._project_name = project_name
        self._branch = branch
        self.auto_detect = auto_detect

    def _get_git_branch(self) -> str:
        """Get current git branch name."""
        if self._branch is not None:
            return self._branch

        if not self.auto_detect:
            return "N/A"

        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return "N/A"

    def _get_ai_info(self) -> str:
        """Get AI provider and model information."""
        if self._ai_info is not None:
            return self._ai_info
        return "N/A"

    def _get_project_name(self) -> str:
        """Get project name."""
        if self._project_name is not None:
            return self._project_name

        if not self.auto_detect:
            return "N/A"

        # Fallback to current directory name
        return Path.cwd().name

    def render(self) -> Table:
        """
        Render the status bar as a Rich Table.

        Returns:
            A Rich Table object with 3 columns (branch, AI info, project).
        """
        # Get status information
        branch = self._get_git_branch()
        ai_info = self._get_ai_info()
        project = self._get_project_name()

        # Create table with no borders
        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            padding=(0, 1),
            expand=True,
            border_style="dim"
        )

        # Add 3 columns with different justifications
        table.add_column(justify="left", ratio=1)   # Branch (left)
        table.add_column(justify="center", ratio=1)  # AI info (center)
        table.add_column(justify="right", ratio=1)   # Project (right)

        # Add the row with styled content
        table.add_row(
            f"[dim]Branch:[/dim] [cyan]{branch}[/cyan]",
            f"[dim]AI:[/dim] [yellow]{ai_info}[/yellow]",
            f"[dim]Project:[/dim] [green]{project}[/green]"
        )

        return table

    def print(self) -> None:
        """
        Render and print the status bar to the console.

        This is a convenience method for quick status bar display.
        """
        table = self.render()
        self.console.print(table)
