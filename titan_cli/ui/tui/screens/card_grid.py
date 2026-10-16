"""
Card Grid Navigation Mixin

Moves the focus across a `Grid` of `WorkflowCard`s when an arrow key is pressed, following
the rule in `grid_navigation.py`.

The arrow keys are declared on the CARD, not here. A card sits inside a `VerticalScroll`,
which binds all four arrows to scrolling and is closer to the focused widget than the screen
is, so screen-level arrow bindings never fired. The card therefore posts
`WorkflowCard.Move(direction)` and this mixin decides where the focus lands - which is the
right split anyway, since the destination depends on the grid's shape and only the screen
knows that.

It is a mixin because the screens that need it already inherit from `BaseScreen`.
"""

from typing import List

from textual.containers import Grid
from textual.css.query import NoMatches

from titan_cli.ui.tui.grid_navigation import Direction, next_focus_index
from titan_cli.ui.tui.widgets import WorkflowCard


class CardGridNavigationMixin:
    """Arrow-key focus movement across a grid of cards.

    A screen mixing this in sets `CARD_GRID_ID` to its grid's id. Nothing has to be added to
    the screen's `BINDINGS`: the keys belong to the card.

    The grid's column count is read back off the widget's own styles, so the number the
    arrows use is the one the layout actually has. Recomputing it from the width here would
    be a second copy of arithmetic the screen already owns, free to disagree with it after a
    resize - the kind of seam this codebase has paid for before.
    """

    CARD_GRID_ID: str = "home-grid"

    def on_workflow_card_move(self, message: WorkflowCard.Move) -> None:
        """An arrow key was pressed on a card."""
        message.stop()
        cards = self._card_grid_cards()
        if not cards:
            return
        try:
            current = cards.index(message.card)
        except ValueError:
            # A card outside this grid posted it; not ours to answer.
            return

        target = next_focus_index(
            current,
            len(cards),
            self._card_grid_columns(),
            Direction(message.direction),
        )
        if target != current:
            cards[target].focus()

    def _card_grid_cards(self) -> List[WorkflowCard]:
        """The grid's focusable cards, in layout order.

        Queried from the grid rather than from the screen, so a card mounted somewhere else -
        or a second grid added later - cannot join the sequence silently.
        """
        try:
            grid = self.query_one(f"#{self.CARD_GRID_ID}", Grid)
        except NoMatches:
            return []
        return [card for card in grid.query(WorkflowCard) if card.can_focus]

    def _card_grid_columns(self) -> int:
        """How many columns the grid is laid out with right now."""
        try:
            grid = self.query_one(f"#{self.CARD_GRID_ID}", Grid)
        except NoMatches:
            return 1
        columns = grid.styles.grid_size_columns
        return columns if columns and columns > 0 else 1
