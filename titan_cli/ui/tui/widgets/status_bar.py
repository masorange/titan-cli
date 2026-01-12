"""
Status Bar Widget

Fixed status bar showing git branch, AI info, and active project.
"""
from textual.widget import Widget
from textual.reactive import reactive
from rich.table import Table as RichTable


class StatusBarWidget(Widget):
    """
    Status bar widget that displays project information.

    Shows:
    - Left: Git branch
    - Center: AI provider and model
    - Right: Active project name

    This widget is designed to be docked at the bottom of the screen.
    """

    # Reactive properties - automatically update the widget when changed
    git_branch: reactive[str] = reactive("N/A")
    ai_info: reactive[str] = reactive("N/A")
    project_name: reactive[str] = reactive("N/A")

    DEFAULT_CSS = """
    StatusBarWidget {
        background: #334155;
        color: #e2e8f0;
        height: 3;
        border-top: solid #3b82f6;
        padding: 0 1;
    }
    """

    def render(self) -> RichTable:
        """
        Render the status bar as a Rich Table.

        Returns:
            Rich Table with 3 columns for branch, AI, and project.
        """
        # Create a Rich table (Textual supports rendering Rich renderables)
        table = RichTable(
            show_header=False,
            show_lines=False,
            box=None,
            expand=True,
            padding=(0, 1),
        )

        table.add_column(justify="left", ratio=1)
        table.add_column(justify="center", ratio=1)
        table.add_column(justify="right", ratio=1)

        table.add_row(
            f"[dim]Branch:[/dim] [cyan]{self.git_branch}[/cyan]",
            f"[dim]AI:[/dim] [yellow]{self.ai_info}[/yellow]",
            f"[dim]Project:[/dim] [green]{self.project_name}[/green]",
        )

        return table

    def update_status(self, git_branch: str = None, ai_info: str = None, project_name: str = None):
        """
        Update status bar information.

        Args:
            git_branch: Git branch name
            ai_info: AI provider/model info
            project_name: Active project name
        """
        if git_branch is not None:
            self.git_branch = git_branch
        if ai_info is not None:
            self.ai_info = ai_info
        if project_name is not None:
            self.project_name = project_name
