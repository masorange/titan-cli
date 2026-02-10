"""
CommentThread Widget

Widget for displaying PR/issue comment threads using PanelContainer.
"""

from typing import Callable, List, Any, Optional
from datetime import datetime
from textual.app import ComposeResult
from textual.widgets import Markdown
from .panel_container import PanelContainer
from .text import BoldText, DimText, Text, DimItalicText
from .prompt_choice import PromptChoice, ChoiceOption
from textual.containers import Horizontal


class CommentThread(PanelContainer):
    """
    Widget for displaying a comment thread.

    Inherits from PanelContainer for consistent theming.
    Includes comment metadata, body, and optional action buttons.
    """

    DEFAULT_CSS = """
    CommentThread.reply {
        margin-left: 4;
    }

    CommentThread PromptChoice {
        margin: 0;
        padding: 0;
        background: transparent;
        border: none;
    }
    """

    def __init__(
        self,
        author: str,
        date: str,
        body: str = None,
        thread_number: str = None,
        is_reply: bool = False,
        is_outdated: bool = False,
        options: Optional[List[ChoiceOption]] = None,
        on_select: Optional[Callable[[Any], None]] = None,
        **kwargs
    ):
        """
        Initialize comment thread widget.

        Args:
            author: Comment author username
            date: Comment date/time
            body: Comment body text (optional)
            thread_number: Thread number text (e.g., "Thread 1 of 8")
            is_reply: Whether this is a reply (indented)
            is_outdated: Whether comment is on outdated code
            options: Optional list of action buttons to display
            on_select: Callback for when an action button is selected
        """
        # Choose variant based on state
        if is_outdated:
            variant = "warning"
        elif is_reply:
            variant = "info"
        else:
            variant = "default"

        # Initialize PanelContainer with variant and title
        super().__init__(variant=variant, title=thread_number, **kwargs)

        self.author = author
        self.date = date
        self.body = body
        self.is_outdated = is_outdated
        self.options = options or []
        self.on_select_callback = on_select

        if is_reply:
            self.add_class("reply")

    def compose(self) -> ComposeResult:
        """Compose comment content and action buttons."""
        # Format date to DD/MM/YYYY HH:mm:ss
        formatted_date = self.date
        try:
            # Try to parse the date string and reformat it
            date_obj = datetime.fromisoformat(str(self.date).replace('Z', '+00:00'))
            formatted_date = date_obj.strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            # If parsing fails, use as-is
            pass

        # Author and date in one line
        yield self._metadata_container(formatted_date)

        # Comment body - use Markdown to render content
        if self.body and self.body.strip():
            markdown_widget = Markdown(self.body)
            markdown_widget.styles.width = "100%"
            markdown_widget.styles.height = "auto"
            markdown_widget.styles.margin = (1, 0)
            yield markdown_widget
        else:
            yield DimItalicText("Skipped comment")

        # Action buttons (if provided) - reuse PromptChoice widget
        if self.options and self.on_select_callback:
            yield Text("")  # Empty line
            yield PromptChoice(
                question="What would you like to do?",
                options=self.options,
                on_select=self.on_select_callback
            )

    def on_mount(self) -> None:
        """Scroll to show this comment thread fully after it's mounted."""
        # Use call_after_refresh to ensure all content is rendered first
        self.call_after_refresh(self._scroll_to_show_buttons)

    def _scroll_to_show_buttons(self) -> None:
        """Find main scroll container and scroll to end to show action buttons."""
        try:
            # Find the workflow-execution-panel (main scroll container)
            parent = self.parent
            while parent:
                if hasattr(parent, 'id') and parent.id == "workflow-execution-panel":
                    # Scroll to end to show buttons
                    parent.scroll_end(animate=False)
                    break
                parent = parent.parent
        except Exception:
            pass

    def _metadata_container(self, formatted_date: str) -> Horizontal:
        """Create a container for author and date metadata."""
        # Create widgets first
        author_widget = BoldText(f"{self.author}")
        author_widget.styles.width = "auto"

        date_text = f" • {formatted_date}"
        if self.is_outdated:
            date_text += " (outdated)"
        date_widget = DimText(date_text)
        date_widget.styles.width = "auto"

        # Create container with children
        container = Horizontal(author_widget, date_widget)
        container.styles.height = "auto"

        return container

__all__ = ["CommentThread"]
