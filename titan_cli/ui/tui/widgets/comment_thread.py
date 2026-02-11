"""
CommentThread Widget

Widget for organizing a PR/issue comment thread (main comment + replies + actions).
"""

from typing import Callable, List, Any, Optional
from textual.app import ComposeResult
from titan_plugin_github.models import PRComment
from .panel_container import PanelContainer
from .comment import Comment
from .text import BoldText, Text, DimText
from .prompt_choice import PromptChoice, ChoiceOption


class CommentThread(PanelContainer):
    """
    Widget for organizing a comment thread.

    Contains:
    - Main comment (with all its content)
    - Replies (if any)
    - Action buttons (if provided)
    """

    DEFAULT_CSS = """
    CommentThread Comment.reply {
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
        pr_comment: PRComment,
        thread_number: str = None,
        is_outdated: bool = False,
        replies: Optional[List[PRComment]] = None,
        options: Optional[List[ChoiceOption]] = None,
        on_select: Optional[Callable[[Any], None]] = None,
        **kwargs,
    ):
        """
        Initialize comment thread widget.

        Args:
            pr_comment: The main PR comment
            thread_number: Thread number (e.g., "Thread 1 of 8")
            is_outdated: Whether comment is on outdated code
            replies: List of reply comments
            options: Action buttons to display
            on_select: Callback for action button selection
        """
        # Determine variant
        variant = "warning" if is_outdated else "default"

        # Initialize PanelContainer with variant and title
        super().__init__(variant=variant, title=thread_number, **kwargs)

        self.pr_comment = pr_comment
        self.is_outdated = is_outdated
        self.replies = replies or []
        self.options = options or []
        self.on_select_callback = on_select

    def _format_comment_metadata(self, comment: PRComment) -> ComposeResult:
        """Format PR comment object metadata for debugging."""
        yield DimText("─── Comment Metadata ───")
        yield DimText(f"ID: {comment.id}")
        if comment.node_id:
            yield DimText(f"Node ID: {comment.node_id}")
        if comment.user:
            yield DimText(f"User: {comment.user.login}")
        yield DimText(f"Created: {comment.created_at}")
        if comment.path:
            yield DimText(f"Path: {comment.path}")
        if comment.line:
            yield DimText(f"Line: {comment.line}")
        if comment.pull_request_review_id:
            yield DimText(f"Review ID: {comment.pull_request_review_id}")
        if comment.in_reply_to_id:
            yield DimText(f"In Reply To: {comment.in_reply_to_id}")
        yield DimText(f"Is Review Comment: {comment.is_review_comment}")
        yield DimText(f"Is Resolved: {comment.is_resolved}")
        if comment.diff_hunk:
            yield DimText(f"Diff Hunk: {len(comment.diff_hunk)} chars")
        if comment.body:
            yield DimText(f"Body: {comment.body}")
        yield DimText("─────────────────────────")
        yield Text("")

    def compose(self) -> ComposeResult:
        """Compose thread: main comment + replies + action buttons."""
        # Main comment metadata
        for widget in self._format_comment_metadata(self.pr_comment):
            yield widget

        # Main comment formatted
        yield Comment(self.pr_comment, is_outdated=self.is_outdated)

        # Replies (if any)
        if self.replies:
            yield Text("")
            yield BoldText(
                f"💬 {len(self.replies)} repl{'y' if len(self.replies) == 1 else 'ies'}:"
            )
            for reply in self.replies:
                # Reply metadata
                for widget in self._format_comment_metadata(reply):
                    yield widget

                # Reply formatted (pass parent to compare diff_hunk)
                reply_widget = Comment(
                    reply,
                    is_outdated=self.is_outdated,
                    parent_comment=self.pr_comment
                )
                reply_widget.add_class("reply")  # Indentation
                yield reply_widget

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
