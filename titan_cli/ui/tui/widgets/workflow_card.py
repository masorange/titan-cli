"""
Workflow Card Widget

One launchable workflow on the home screen: its number key, its title, the group it
belongs to, and its description.

The focus style carries more weight here than in a list. A grid has no cursor of its own,
so if the focused card is not unmistakable at a glance the user cannot tell what Enter is
about to run.
"""

import textwrap

from textual.binding import Binding
from textual.message import Message
from textual.widgets import Static

from titan_cli.ui.tui.icons import Icons
from .collapsible_list import escape_markup


# How many rows of the fixed-height card the description gets. The budget in characters
# is derived from this and the card's REAL width, because a fixed character count cannot
# know it: 110 characters is untouched prose in one column and two clipped lines in four.
DESCRIPTION_ROWS = 2


class WorkflowCard(Static):
    """
    A focusable card that launches one workflow.

    Args:
        workflow_name: Name used to launch the workflow, and the message payload.
        title: Display title.
        group: Group the workflow belongs to, as `detect_plugin_name()` reports it.
        description: One-line summary; wrapped by the card, not truncated here.
        key: Number key that launches it, or None when it is past the key range.
        is_favorite: Whether the user starred it.
    """

    can_focus = True

    BINDINGS = [
        Binding("enter", "launch", "Launch", show=False),
    ]

    DEFAULT_CSS = """
    WorkflowCard {
        width: 1fr;
        height: 9;
        border: round $primary;
        border-title-align: left;
        /* Vertical padding is what the first version got wrong: the title sat flush
           against the border and the description ran into the bottom edge. */
        padding: 1 2;
        background: $surface-lighten-1;
    }

    WorkflowCard:focus {
        border: round $accent;
        background: $accent 15%;
    }

    WorkflowCard:hover {
        border: round $accent;
    }
    """

    class Selected(Message):
        """Sent when a card is chosen, by Enter or by click."""

        def __init__(self, workflow_name: str) -> None:
            super().__init__()
            self.workflow_name = workflow_name

    def __init__(
        self,
        workflow_name: str,
        title: str,
        group: str,
        description: str = "",
        key: int = None,
        is_favorite: bool = False,
        **kwargs,
    ):
        self.workflow_name = workflow_name
        self.card_title = title
        self.group = group
        self.description = description
        self.key = key
        self.is_favorite = is_favorite
        # Width the body was last rendered for, so a Resize that did not change it is a
        # no-op rather than another render.
        self._rendered_width = 0
        super().__init__(self._render_body(), **kwargs)
        self.border_title = self._render_border_title()

    def _render_border_title(self) -> str:
        """The key, starred when the workflow is a favorite.

        A favorite past the key range still gets its star, so D-007's extra rows read as
        workflows the user chose rather than as filler.
        """
        parts = []
        if self.is_favorite:
            parts.append(Icons.STAR)
        if self.key is not None:
            parts.append(str(self.key))
        return " ".join(parts)

    def _render_body(self) -> str:
        """Title, group, a blank line, then the description.

        The blank line is load-bearing: the title, the group and the description are three
        different kinds of information, and run together they read as one paragraph.

        Titles and descriptions come out of workflow YAML, so they are escaped: a
        description containing `[something]` would otherwise be eaten as markup, or raise
        and take the whole card render down with it.
        """
        title = escape_markup(self.card_title)
        group = escape_markup(self.group)
        body = f"[bold]{title}[/bold]\n[dim]{group}[/dim]"
        if self.description:
            body = f"{body}\n\n{escape_markup(self._clipped_description())}"
        return body

    def _clipped_description(self) -> str:
        """The description, cut to the rows this card actually has for it.

        Wrapped here rather than budgeted in characters, because neither a fixed character
        count nor `width * rows` can predict where the text breaks: wrapping leaves ragged
        space at each line end, so both overestimate and let a third line spill past the
        fixed-height box - which is exactly how the first two versions of this clipped
        mid-word with no ellipsis.
        """
        try:
            width = self.content_size.width
        except Exception:
            # Reading the width needs a screen to measure against, and this runs from
            # __init__ too. Before the first layout there is none; on_resize re-renders
            # once there is.
            width = 0
        if not width:
            return self.description

        lines = textwrap.wrap(self.description, width=width)
        if len(lines) <= DESCRIPTION_ROWS:
            return self.description

        kept = lines[:DESCRIPTION_ROWS]
        last = kept[-1]
        if len(last) + 1 > width:
            last = last[: width - 1].rstrip()
        kept[-1] = f"{last}…"
        return "\n".join(kept)

    def on_resize(self) -> None:
        """Re-budget the description against the new width, at most once per width.

        Guarded on the width having actually changed. Calling `update()` unconditionally
        re-renders, which can change layout, which emits another Resize - a feedback loop
        that never settles. It showed up as a Textual "timed out waiting for widgets to
        process pending messages", not as a visible spin.
        """
        try:
            width = self.content_size.width
        except Exception:
            return
        if width == self._rendered_width:
            return
        self._rendered_width = width
        self.update(self._render_body())

    def action_launch(self) -> None:
        """Ask the screen to launch this workflow."""
        self.post_message(self.Selected(self.workflow_name))

    def on_click(self) -> None:
        """Clicking a card focuses it and launches it."""
        self.focus()
        self.action_launch()
