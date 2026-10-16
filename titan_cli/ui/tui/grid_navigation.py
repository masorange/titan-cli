"""
Grid Navigation

Where the focus goes when an arrow key is pressed in a grid of focusable widgets.

Textual's `Screen` binds only `tab`/`shift+tab` for focus, so arrow keys do nothing in a
grid of cards by default - measured against the running home, where all four arrows left the
focus where it was while three tabs walked the grid. An `OptionList` gives up/down for free,
so a card grid without this is a step backwards from the list it replaces.

The rule lives here as one pure function of indices, deliberately knowing nothing about
widgets: it is the only part of arrow navigation that can be tested without mounting a
screen, and mounting is not available to us (the domain writes no UI tests).
"""

from enum import Enum


class Direction(Enum):
    """Which way the user asked to go."""

    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


def next_focus_index(
    current: int,
    count: int,
    columns: int,
    direction: Direction,
) -> int:
    """Index the focus moves to, or `current` when the move is not possible.

    The grid is row-major: index `i` sits at row `i // columns`, column `i % columns`, which
    is how Textual lays a `Grid` out.

    Edges do not wrap. Left at the first card and right at the last stay put, because a grid
    has a visible shape and a focus that leaps from one corner to the opposite one reads as a
    glitch rather than as navigation. `tab` still wraps, and that difference is deliberate:
    `tab` is a sequence, arrows are a map.

    The one asymmetry is **down out of a full row into a short last row**. Moving down from
    the middle of the second row when the third holds a single card would otherwise do
    nothing, leaving that card reachable only by `tab`. Instead the focus lands on the last
    card. Up has no equivalent case: the first row is never short.

    Args:
        current: Index currently focused.
        count: How many focusable items the grid holds.
        columns: Items per row, as the grid is laid out right now.
        direction: Which way to move.

    Returns:
        The new index, clamped into `range(count)`. Returns `current` unchanged when the
        move is impossible, so a caller can skip the focus call entirely.
    """
    if count <= 0:
        return current
    if columns <= 0:
        # A grid mid-layout can report zero columns; treat it as a single column rather
        # than dividing by it.
        columns = 1

    current = max(0, min(current, count - 1))

    if direction is Direction.LEFT:
        return current - 1 if current > 0 else current

    if direction is Direction.RIGHT:
        return current + 1 if current < count - 1 else current

    if direction is Direction.UP:
        target = current - columns
        return target if target >= 0 else current

    # DOWN
    target = current + columns
    if target < count:
        return target
    # Past the end: land on the last card if there is a row below at all, otherwise stay.
    if current // columns < (count - 1) // columns:
        return count - 1
    return current
