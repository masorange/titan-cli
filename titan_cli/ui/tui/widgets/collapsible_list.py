"""
A list of expandable entries — summary line visible, detail on demand.

Deliberately free of any domain knowledge: it takes titles and bodies and
returns a widget.

List+detail is a shape that recurs — log events, PR review findings, Crashlytics
issues — so this lives in the shared widget set rather than in whichever plugin
needed it first. Mount it from a step with `ctx.textual.collapsible_list(entries)`,
or build the tree yourself with `build_collapsible_list` and mount it by hand.
"""

from dataclasses import dataclass, field
from typing import Optional, Union

from rich.console import RenderableType

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Collapsible, Label, Static
from textual.widgets._collapsible import CollapsibleTitle

from titan_cli.ui.tui.clipboard import copy_to_system_clipboard


#: Blank columns kept between the name and the block anchored to the right edge,
#: so a name that fills the row does not arrive touching the duration.
GUTTER = 2

#: Room the fold triangle and its space take in front of a title.
SYMBOL_WIDTH = 2

#: Blank columns after the copy button, so the row does not end flush against
#: the edge of the panel.
RIGHT_MARGIN = 2


def elide(text: str, width: int) -> str:
    """
    Cut `text` to `width`, marking the cut. Never pads.

    A width too small for even the ellipsis returns nothing rather than a stray
    character: at that point the row has no room to say anything anyway.
    """
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return "…"

    cut = text[:width - 1]
    # `escape_markup` writes `\[`, and cutting between the two would leave a
    # trailing backslash on screen and an unbalanced escape behind it.
    if cut.endswith("\\"):
        cut = cut[:-1]
    return cut + "…"


def _styled(text: str, style: str) -> str:
    """
    Wrap in Rich markup, after cutting and never before.

    The style has to be applied to the fitted text rather than carried inside it,
    or the cut lands in the middle of a `[dim]` and the tag is what reaches the
    screen. Same order anything that both cuts and escapes has to apply.
    """
    return f"[{style}]{text}[/]" if style else text


class ElasticTitle(CollapsibleTitle):
    """
    A title that fits itself to the width it is given, on every resize.

    Textual 1.0 has no `text-overflow`, so this cannot be left to CSS: the widget
    has to measure and cut. It matters because the alternative is a fixed column,
    which cuts a long name at the same place on every row while half the line sits
    empty to its right.
    """

    def __init__(self, *, full_label: str, style: str = "", **kwargs) -> None:
        super().__init__(label=_styled(full_label, style), **kwargs)
        self._full_label = full_label
        self._style = style

    def on_resize(self) -> None:
        fitted = _styled(elide(self._full_label, self.size.width - SYMBOL_WIDTH),
                         self._style)
        # Guarded because assigning to `label` re-renders: it changes the content
        # and not the width, so it cannot re-trigger a resize, but writing on
        # every resize event for no reason is still work nobody asked for.
        if fitted != self.label:
            self.label = fitted


class ElasticLabel(Label):
    """The same fitting, for a row that has nothing to fold open."""

    DEFAULT_CSS = """
    ElasticLabel {
        color: $foreground;
        height: 1;
        width: 1fr;
    }
    """

    def __init__(self, text: str, style: str = "", **kwargs) -> None:
        super().__init__(_styled(text, style), markup=True, **kwargs)
        self._full_text = text
        self._style = style

    def on_resize(self) -> None:
        self.update(_styled(elide(self._full_text, self.size.width), self._style))


class RightBlock(Static):
    """
    Duration and effect, against the right edge of the row.

    They are scanned down a column rather than read, which is what being against
    an edge buys — and it leaves the whole rest of the row to the name, which is
    the part that was being cut while half the line sat empty.

    It states its colour for the reason `PlainEntry` does: a `Static` inherits
    whatever the surrounding panel is painted in, and in the workflow output that
    is green. This text used to live inside the `CollapsibleTitle`, which brings
    its own colour, so moving it out turned every store name green.
    """

    DEFAULT_CSS = """
    RightBlock {
        width: auto;
        height: 1;
        padding: 0 0 0 %d;
        color: $foreground;
    }
    """ % GUTTER


class CopyButton(Static):
    """
    Copy this entry's content to the clipboard.

    No border: a bordered box is three rows tall in a terminal, and on a list
    where every row is one line that would treble the height of the whole view.
    The affordance is the glyph plus what happens on hover, which costs nothing.

    A local clipboard helper is tried first and OSC 52 only as a fallback, for
    the reason in `clipboard.py`: the escape sequence is fire-and-forget and
    several common terminals ignore it, so the first version put nothing on the
    clipboard and said "Copied" anyway. The notification now distinguishes the
    two — a copy that may not have landed must not read like one that did.
    """

    GLYPH = "⧉"

    DEFAULT_CSS = """
    CopyButton {
        width: 3;
        height: 1;
        color: $text-muted;
        text-align: center;
        &:hover {
            color: $accent;
            background: $boost;
        }
    }
    """

    def __init__(self, text: str, label: str = "") -> None:
        super().__init__(self.GLYPH)
        self._text = text
        self._label = label
        self.tooltip = f"Copy {label}" if label else "Copy"

    def on_click(self) -> None:
        what = self._label or "row"

        if copy_to_system_clipboard(self._text):
            self.notify(f"Copied {what}", timeout=2)
            return

        # Nothing local took it: this is a remote session, or the helpers are not
        # installed. OSC 52 is the only route left and it cannot be confirmed,
        # so the message says what was attempted rather than claiming success.
        self.app.copy_to_clipboard(self._text)
        self.notify(f"Sent {what} to the terminal's clipboard — if nothing pastes, "
                    "this terminal does not support it",
                    severity="warning", timeout=5)


class ListEntry(Collapsible):
    """
    A collapsible without Textual's block cursor.

    The default focus style paints the whole title row in the accent colour, which
    on a long list reads as "this row is selected/highlighted" and stays there
    after you toggle it. The row is not selected — it is merely focused.

    The cue is not removed, only quietened: bold plus a left bar. Dropping it
    entirely would leave keyboard navigation with no way to say where you are.
    """

    DEFAULT_CSS = """
    ListEntry CollapsibleTitle:focus {
        background: transparent;
        text-style: bold;
        border-left: thick $accent;
    }
    ListEntry CollapsibleTitle:hover {
        background: $boost;
    }
    ListEntry:focus-within {
        background-tint: transparent;
    }
    ListEntry .entry-head {
        height: auto;
        width: 100%%;
        padding: 0 %d 0 0;
    }
    ListEntry .entry-head CollapsibleTitle {
        width: 1fr;
    }
    """ % RIGHT_MARGIN

    def __init__(self, *contents, title: str, collapsed: bool,
                 style: str = "", right: str = "",
                 pending: Optional[list["CollapsibleEntry"]] = None,
                 body_colour: str = "", copy_text: str = "",
                 copy_label: str = "") -> None:
        super().__init__(*contents, title=title, collapsed=collapsed)
        # Textual builds a fixed-width title in its own `__init__`; this one has
        # to re-fit itself whenever the row changes width, so it is swapped in
        # before anything is mounted.
        self._title = ElasticTitle(full_label=title, style=style,
                                   collapsed_symbol=self._title.collapsed_symbol,
                                   expanded_symbol=self._title.expanded_symbol,
                                   collapsed=collapsed)
        self._right = right
        #: Sub-entries not built yet. Building the whole tree up front costs
        #: thousands of widgets and seconds before the first frame on a large list,
        #: all of it for detail that starts hidden. They are built the first time
        #: this entry is opened, once.
        self._pending = list(pending or [])
        self._body_colour = body_colour
        self._copy_text = copy_text
        self._copy_label = copy_label

    def compose(self) -> ComposeResult:
        """
        Title and copy button on one row, contents below.

        Textual's own `compose` yields the title and the contents; the title is
        put in a row beside the button instead, so copying does not require
        opening the entry first. A row with nothing to copy yields the title
        exactly as Textual would.

        The row is sized by `.entry-head` in the CSS above, and it has to be:
        `Horizontal` defaults to `height: 1fr`, so the first row with a copy
        button took the whole viewport and pushed every row after it off the
        screen. Same trap as the container in `build_collapsible_list`.
        """
        with Horizontal(classes="entry-head"):
            yield self._title
            if self._right:
                yield RightBlock(self._right)
            if self._copy_text:
                yield CopyButton(self._copy_text, self._copy_label)

        yield self.Contents(*self._contents_list)

    def on_collapsible_expanded(self, event: Collapsible.Expanded) -> None:
        # Expanded bubbles, so a parent hears its children open too.
        if event.collapsible is not self or not self._pending:
            return

        pending, self._pending = self._pending, []
        self.query_one(Collapsible.Contents).mount(
            *[_widget_for(child, self._body_colour) for child in pending]
        )


class PlainEntry(Label):
    """
    An entry with nothing behind it.

    It exists for its colour. A `Label` inherits whatever the surrounding panel
    is painted in — in the workflow output that is green — while a `Collapsible`
    brings its own, so the lines with the least to say came out the loudest on
    screen. Stating the colour puts a line and a collapsible on equal footing;
    anything quieter than that is then a deliberate choice by the caller.
    """

    DEFAULT_CSS = """
    PlainEntry {
        color: $foreground;
        height: auto;
    }
    """


@dataclass
class CollapsibleEntry:
    """One line of the list, plus whatever it hides."""
    title: str
    #: Plain text, Rich markup, or any Rich renderable. Textual is built on Rich
    #: and its widgets take renderables directly, so a highlighted block can be
    #: passed as data instead of as a markup string nobody has to escape.
    body: list[Union[str, RenderableType]] = field(default_factory=list)
    #: Content colour. Body text inherits the output panel's green otherwise, which
    #: makes payloads read as status rather than as data.
    body_colour: str = "#d8d8d8"
    children: list["CollapsibleEntry"] = field(default_factory=list)
    expanded: bool = False
    style: Optional[str] = None      # Rich markup, e.g. "bold red"
    #: Short text anchored to the right edge of the row — a duration, an effect.
    #: Kept apart from the title so the title can use every column left over.
    right: str = ""
    #: What the copy button puts on the clipboard. The caller decides — for a
    #: parsed payload the source text is what you want to paste somewhere else,
    #: not the tree it was laid out as. Empty means no button.
    copy_text: str = ""
    #: Named in the confirmation, so "Copied response body" says which of the
    #: four buttons on a request was pressed.
    copy_label: str = ""


def build_collapsible_list(entries: list[CollapsibleEntry], classes: str = "") -> Vertical:
    """
    Build the widget tree. No mounting, no threads — the caller owns both.

    The container is sized to its content. Textual gives `Vertical` a default
    height of `1fr`, which means "take the space the parent offers": mounted inside
    a step's output that produced a box a couple of lines tall, clipping everything
    below and leaving nothing to scroll. `auto` makes it grow with the list so the
    surrounding scroll view can do its job.

    Only the top level is built here. Everything behind a closed triangle is built
    the first time that triangle is opened — see `ListEntry`.
    """
    container = Vertical(*[_widget_for(entry) for entry in entries], classes=classes)
    container.styles.height = "auto"
    container.styles.width = "100%"
    return container


def _widget_for(entry: CollapsibleEntry, inherited_colour: str = "") -> Widget:
    colour = entry.body_colour or inherited_colour
    style = entry.style or ""

    body: list[Widget] = []
    for text in entry.body:
        static = Static(text)
        static.styles.height = "auto"
        static.styles.color = colour
        body.append(static)

    # An entry with nothing behind it is a line, not a collapsible: a triangle
    # that opens onto emptiness reads as a bug.
    if not body and not entry.children:
        # Two spaces stand in for the collapsed triangle, so a line with no detail
        # still lines up with the ones that have it. Without this the list looks
        # broken rather than merely mixed.
        line = ElasticLabel(f"  {entry.title}", style)
        parts: list[Widget] = [line]
        if entry.right:
            parts.append(RightBlock(entry.right))
        # Nothing to open does not mean nothing to copy: a row whose name is cut
        # on screen is exactly the one worth pasting somewhere else.
        if entry.copy_text:
            parts.append(CopyButton(entry.copy_text, entry.copy_label))

        row = Horizontal(*parts, classes="entry-head")
        row.styles.height = "auto"
        # The collapsible rows get this from the stylesheet; this one is built
        # by hand and would otherwise end flush against the edge.
        row.styles.padding = (0, RIGHT_MARGIN, 0, 0)
        return row

    # A closed entry's sub-entries are built when it is first opened; an open one
    # needs them now, or it would expand onto nothing.
    if entry.expanded:
        body += [_widget_for(child, colour) for child in entry.children]
        pending = []
    else:
        pending = entry.children

    collapsible = ListEntry(*body, title=entry.title, collapsed=not entry.expanded,
                            style=style, right=entry.right,
                            pending=pending, body_colour=colour,
                            copy_text=entry.copy_text, copy_label=entry.copy_label)
    # Same reason as the container: an expanded entry must add its own height
    # instead of squeezing its content into whatever was left over.
    collapsible.styles.height = "auto"
    return collapsible


def escape_markup(text: str) -> str:
    """
    Neutralise Rich markup in content that came from outside.

    Log payloads contain things like `[MOBILE, LANDLINE]` and `[/bold]`; rendered
    as markup they either vanish or raise.
    """
    return text.replace("[", r"\[")
