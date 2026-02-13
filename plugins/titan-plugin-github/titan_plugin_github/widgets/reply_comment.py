"""
ReplyComment Widget

Widget for displaying reply comments in a review thread.
Shows only: author, date, and comment body (context already shown in main comment).
"""

from typing import List, Any
from textual.app import ComposeResult
from textual.widget import Widget
from textual.containers import Horizontal
from ..models import UIComment
from titan_cli.ui.tui.widgets import BoldText, DimText, DimItalicText, Text
from .comment_utils import render_comment_elements


class ReplyComment(Widget):
    """
    Widget for displaying a reply comment in a review thread.

    Shows only author, date, and body - no file path, line, or diff context
    since those are already shown in the main comment.
    """

    DEFAULT_CSS = """
    ReplyComment {
        width: 100%;
        height: auto;
    }

    ReplyComment Horizontal {
        width: 100%;
    }
    """

    def __init__(self, reply: UIComment, **kwargs):
        """
        Initialize reply comment widget.

        Args:
            reply: The UI comment to display
        """
        super().__init__(**kwargs)
        self.reply = reply

    def compose(self) -> ComposeResult:
        """Compose reply comment (author + date + body only)."""
        # Author and date
        yield self._metadata_container()
        yield Text("")

        # Comment body (no file info or code context)
        if self.reply.body and self.reply.body.strip():
            for widget in self._parse_and_render_body():
                yield widget
        else:
            yield DimItalicText("(empty reply)")

    def _metadata_container(self) -> Horizontal:
        """Create container for author and date metadata."""
        author_widget = BoldText(f"{self.reply.author_name}")
        author_widget.styles.width = "auto"

        date_widget = DimText(f" • {self.reply.formatted_date}")
        date_widget.styles.width = "auto"

        container = Horizontal(author_widget, date_widget)
        container.styles.height = "auto"

        return container

    def _parse_and_render_body(self) -> List[Any]:
        """Parse reply body and render as Textual widgets."""
        return render_comment_elements(
            body=self.reply.body,
            diff_hunk=self.reply.diff_hunk,
            line=self.reply.line
        )

__all__ = ["ReplyComment"]
