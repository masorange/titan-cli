"""
CommentThread Widget

Widget for organizing a PR review comment thread (main comment + replies + actions).
Uses GraphQL structure for clean separation.
"""

from typing import Callable, List, Any, Optional
from textual.app import ComposeResult
from ..models import UICommentThread
from titan_cli.ui.tui.widgets import PanelContainer, BoldText, Text, PromptChoice, ChoiceOption
from .comment_view import CommentView
from .reply_comment import ReplyComment


class _ReplyPanel(PanelContainer):
    """Internal widget for rendering a reply comment in a bordered panel."""

    def __init__(self, reply_widget: ReplyComment, **kwargs):
        super().__init__(variant="default", **kwargs)
        self.reply_widget = reply_widget
        self.add_class("reply-panel")

    def compose(self) -> ComposeResult:
        """Render the reply comment inside the panel."""
        yield self.reply_widget


class _VerdictPanel(PanelContainer):
    """What the judging session concluded about this comment, in the thread it belongs to.

    It sits between the comment and the options because that is where it is read: above the
    thread it scrolls away behind the diff and the replies, and by the time the buttons are
    on screen there is nothing left saying what was judged.

    `PanelContainer` and not `Panel`: the latter is `width: auto`, so a verdict's reason -
    one long sentence, plus the files and the callers - runs off the right edge instead of
    wrapping.
    """

    def __init__(self, lines: List[tuple], variant: str = "default", **kwargs):
        super().__init__(variant=variant, title="AI verdict", **kwargs)
        self.lines = lines

    def compose(self) -> ComposeResult:
        for label, value in self.lines:
            if label:
                yield BoldText(label)
            yield Text(value)


class CommentThread(PanelContainer):
    """
    Widget for organizing a review comment thread (GraphQL structure).

    Simplified to use UICommentThread which already contains:
    - main_comment: UIComment
    - replies: List[UIComment]
    - is_resolved: bool
    - is_outdated: bool
    """

    DEFAULT_CSS = """
    CommentThread PanelContainer.reply-panel {
        margin-left: 4;
        border: round white;
    }

    CommentThread.outdated-thread {
        border: round $warning;
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
        thread: UICommentThread,
        thread_number: Optional[str] = None,
        options: Optional[List[ChoiceOption]] = None,
        on_select: Optional[Callable[[Any], None]] = None,
        verdict_lines: Optional[List[tuple]] = None,
        verdict_variant: str = "default",
        **kwargs,
    ):
        """
        Initialize comment thread widget.

        Args:
            thread: UICommentThread with main_comment, replies, and metadata
            thread_number: Thread number (e.g., "Thread 1 of 8")
            options: Action buttons to display
            on_select: Callback for action button selection
            verdict_lines: (heading, text) pairs from the judging session, shown right above
                the options; empty or None when no session judged this comment
            verdict_variant: Border variant for that panel
        """
        # Always use default variant - outdated styling is CSS-only
        super().__init__(variant="default", title=thread_number, **kwargs)

        self.thread = thread
        self.options = options or []
        self.on_select_callback = on_select
        self.verdict_lines = verdict_lines or []
        self.verdict_variant = verdict_variant

        # Add CSS class for outdated threads (only affects border color)
        if thread.is_outdated:
            self.add_class("outdated-thread")

    def compose(self) -> ComposeResult:
        """Compose thread: main comment + replies + action buttons."""
        # Main comment (with full context: path, line, diff_hunk, body)
        if self.thread.main_comment:
            yield CommentView.from_ui_comment(
                self.thread.main_comment,
                is_outdated=self.thread.is_outdated,
            )

        # Replies (if any)
        if self.thread.replies:
            yield Text("")
            yield BoldText(
                f"💬 {len(self.thread.replies)} repl{'y' if len(self.thread.replies) == 1 else 'ies'}:"
            )
            for reply in self.thread.replies:
                # Create ReplyComment widget (only author, date, body)
                reply_widget = ReplyComment(reply=reply)

                # Wrap in panel with border
                yield _ReplyPanel(reply_widget=reply_widget)

        # The verdict, last before the options: it is what the choice is made on.
        if self.verdict_lines:
            yield _VerdictPanel(self.verdict_lines, variant=self.verdict_variant)

        # Action buttons (if provided)
        if self.options and self.on_select_callback:
            yield Text("")  # Empty line
            yield PromptChoice(
                question="What would you like to do?",
                options=self.options,
                on_select=self.on_select_callback
            )

    def on_mount(self) -> None:
        """Scroll to show this comment thread fully after it's mounted."""
        self.call_after_refresh(self._scroll_to_show_buttons)

    def _scroll_to_show_buttons(self) -> None:
        """Find main scroll container and scroll to end to show action buttons."""
        try:
            # Find the workflow-execution-panel (main scroll container)
            parent = self.parent
            while parent:
                if hasattr(parent, 'id') and parent.id == "workflow-execution-panel":
                    parent.scroll_end(animate=False)
                    break
                parent = parent.parent
        except Exception:
            pass


__all__ = ["CommentThread"]

