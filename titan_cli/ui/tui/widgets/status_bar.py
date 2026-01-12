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
        height: 3;
        width: 100%;
    }

    StatusBarWidget Horizontal {
        width: 100%;
        height: 100%;
    }

    StatusBarWidget Static {
        width: 1fr;
        height: 100%;
        content-align: center middle;
    }

    StatusBarWidget #branch-info {
        text-align: left;
    }

    StatusBarWidget #ai-info {
        text-align: center;
    }

    StatusBarWidget #project-info {
        text-align: right;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the status bar with three columns."""
        with Horizontal():
            yield Static("Branch: N/A", id="branch-info")
            yield Static("AI: N/A", id="ai-info")
            yield Static("Project: N/A", id="project-info")

    # Temporarily disabled for debugging
    # def on_mount(self) -> None:
    #     """Initialize the status bar content when mounted."""
    #     self._update_branch(self.git_branch)
    #     self._update_ai(self.ai_info)
    #     self._update_project(self.project_name)

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
