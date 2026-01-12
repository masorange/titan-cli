"""
Status Bar Component (View)

Visual component that displays project status information in 3 columns:
- Left: Git branch
- Center: AI provider and model
- Right: Active project

This is a view component because it composes multiple UI elements.
"""

from typing import Optional

from titan_plugin_git.models import GitStatus
from ..components.table import TableRenderer


class StatusBarRenderer:
    """
    Renders a status bar showing git branch, AI config, and active project.

    The status bar is designed to be displayed at the bottom of menus and
    provide quick context about the current environment.
    """

    def __init__(
        self,
        table_renderer: TableRenderer,
        git_status: Optional[GitStatus] = None,
        ai_info: Optional[str] = None,
        project_name: Optional[str] = None,
    ):
        """
        Initialize the StatusBarRenderer.

        Args:
            table_renderer: An instance of the TableRenderer.
            git_status: A GitStatus object.
            ai_info: AI provider/model info (e.g., "anthropic/claude-3").
            project_name: Project name to display.
        """
        self.table_renderer = table_renderer
        self.git_status = git_status
        self.ai_info = ai_info or "N/A"
        self.project_name = project_name or "N/A"

    def render(self):
        """
        Render the status bar as a Rich Table.

        Returns:
            A Rich Table object with 3 columns (branch, AI info, project).
        """
        branch = self.git_status.branch if self.git_status else "N/A"

        # Add the row with styled content
        return self.table_renderer.render(
            headers=["", "", ""],
            rows=[
                [
                    f"[dim]Branch:[/dim] [cyan]{branch}[/cyan]",
                    f"[dim]AI:[/dim] [yellow]{self.ai_info}[/yellow]",
                    f"[dim]Project:[/dim] [green]{self.project_name}[/green]",
                ]
            ],
            show_header=False,
            show_lines=False,
            box_style="none",
            expand=True,
        )

    def print(self) -> None:
        """
        Render and print the status bar to the console.

        This is a convenience method for quick status bar display.
        """
        table = self.render()
        self.table_renderer.console.print(table)
