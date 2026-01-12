"""
Status Bar Widget

Fixed status bar showing git branch, AI info, and active project.
"""
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static
from textual.containers import Horizontal
from textual.reactive import reactive

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
        color: white;
        height: 1;
        width: 100%;
    }

    StatusBarWidget Horizontal {
        width: 100%;
    }

    StatusBarWidget Static {
        width: 1fr;
        height: 100%;
        content-align: center middle;
    }

    StatusBarWidget #branch-info {
        text-align: left;
        color: blue;
    }

    StatusBarWidget #ai-info {
        text-align: center;
        color: green;
    }

    StatusBarWidget #project-info {
        text-align: right;
        color: orange;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the status bar with three columns."""
        with Horizontal():
            yield Static(f"{self.git_branch}", id="branch-info")
            yield Static(f"{self.ai_info}", id="ai-info")
            yield Static(f"{self.project_name}", id="project-info")

    def _update_branch(self, value: str) -> None:
        """Update branch display."""
        branch_widget = self.query_one("#branch-info", Static)
        branch_widget.update(value)

    def _update_ai(self, value: str) -> None:
        """Update AI display."""
        ai_widget = self.query_one("#ai-info", Static)
        ai_widget.update(value)

    def _update_project(self, value: str) -> None:
        """Update project display."""
        project_widget = self.query_one("#project-info", Static)
        project_widget.update(value)

    def watch_git_branch(self, new_value: str) -> None:
        """Update branch display when git_branch changes."""
        if self.is_mounted:
            self._update_branch(new_value)

    def watch_ai_info(self, new_value: str) -> None:
        """Update AI display when ai_info changes."""
        if self.is_mounted:
            self._update_ai(new_value)

    def watch_project_name(self, new_value: str) -> None:
        """Update project display when project_name changes."""
        if self.is_mounted:
            self._update_project(new_value)

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