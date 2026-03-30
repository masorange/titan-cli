"""
CommentRefinementWidget

Widget for the iterative AI code review refinement loop.

Shows a PR comment thread alongside the current AI-generated suggestion,
an iteration counter, and Approve / Reject / Refine action buttons.

The step manages the threading.Event pattern; this widget only holds the visual
representation for one iteration and calls the provided on_select callback with
a RefinementAction value.
"""

from typing import Callable, List, Optional

from textual.app import ComposeResult
from textual.widgets import Markdown, Static

from titan_cli.core.models.code_review import RefinementAction
from titan_cli.ui.tui.widgets import (
    BoldText,
    ChoiceOption,
    DimText,
    PanelContainer,
    PromptChoice,
    Text,
)

from ..models import UICommentThread
from .comment_view import CommentView
from .reply_comment import ReplyComment


class _ReplyPanel(PanelContainer):
    """Internal panel for a single reply inside a refinement widget."""

    def __init__(self, reply_widget: ReplyComment, **kwargs):
        super().__init__(variant="default", **kwargs)
        self.reply_widget = reply_widget
        self.add_class("reply-panel")

    def compose(self) -> ComposeResult:
        yield self.reply_widget


class CommentRefinementWidget(PanelContainer):
    """
    Displays a PR comment thread, the current AI suggestion, and
    Approve / Reject / Refine action buttons.

    Args:
        thread: The PR comment thread to display.
        suggestion: Current AI-generated reply suggestion (plain text or markdown).
        iteration: Current iteration number (1-based).
        max_iterations: Maximum allowed iterations before warning.
        thread_label: Label shown in the panel title, e.g. "Thread 2 of 5".
        on_select: Callback invoked with a RefinementAction value.
    """

    DEFAULT_CSS = """
    CommentRefinementWidget {
        width: 100%;
        height: auto;
    }

    CommentRefinementWidget .reply-panel {
        margin-left: 4;
        border: round white;
    }

    CommentRefinementWidget .iteration-badge {
        width: auto;
        height: 1;
        padding: 0 2;
        margin: 1 0;
        color: $accent;
    }

    CommentRefinementWidget .iteration-badge.at-limit {
        color: $warning;
    }

    CommentRefinementWidget .suggestion-label {
        margin-top: 1;
    }

    CommentRefinementWidget PromptChoice {
        margin: 0;
        padding: 0;
        background: transparent;
        border: none;
    }
    """

    def __init__(
        self,
        thread: UICommentThread,
        suggestion: str,
        iteration: int,
        max_iterations: int,
        thread_label: Optional[str] = None,
        on_select: Optional[Callable[[RefinementAction], None]] = None,
        **kwargs,
    ):
        super().__init__(variant="default", title=thread_label or None, **kwargs)
        self.thread = thread
        self.suggestion = suggestion
        self.iteration = iteration
        self.max_iterations = max_iterations
        self.on_select_callback = on_select

    def compose(self) -> ComposeResult:
        # ── Original comment ─────────────────────────────────────────────────
        if self.thread.main_comment:
            yield CommentView.from_ui_comment(
                self.thread.main_comment,
                is_outdated=self.thread.is_outdated,
            )

        # ── Replies ──────────────────────────────────────────────────────────
        if self.thread.replies:
            yield Text("")
            reply_count = len(self.thread.replies)
            yield BoldText(
                f"💬 {reply_count} repl{'y' if reply_count == 1 else 'ies'}:"
            )
            for reply in self.thread.replies:
                yield _ReplyPanel(reply_widget=ReplyComment(reply=reply))

        # ── Iteration badge ──────────────────────────────────────────────────
        iteration_text = f"✦ Iteration {self.iteration} / {self.max_iterations}"
        badge = Static(iteration_text)
        badge.add_class("iteration-badge")
        if self.iteration >= self.max_iterations:
            badge.add_class("at-limit")
        yield badge

        # ── AI suggestion ────────────────────────────────────────────────────
        yield DimText("AI Suggestion:", classes="suggestion-label")
        yield Markdown(self.suggestion)

        # ── Action buttons ───────────────────────────────────────────────────
        yield Text("")
        options: List[ChoiceOption] = [
            ChoiceOption(value=RefinementAction.APPROVE, label="✓ Approve", variant="success"),
            ChoiceOption(value=RefinementAction.REJECT, label="✗ Reject", variant="error"),
            ChoiceOption(value=RefinementAction.REFINE, label="💬 Refine", variant="default"),
        ]
        yield PromptChoice(
            question="What would you like to do with this suggestion?",
            options=options,
            on_select=self.on_select_callback,
        )

    def on_mount(self) -> None:
        """Scroll to show buttons after mounting."""
        self.call_after_refresh(self._scroll_to_show_buttons)

    def _scroll_to_show_buttons(self) -> None:
        try:
            parent = self.parent
            while parent:
                if hasattr(parent, "id") and parent.id == "workflow-execution-panel":
                    parent.scroll_end(animate=False)
                    break
                parent = parent.parent
        except Exception:
            pass


__all__ = ["CommentRefinementWidget"]
