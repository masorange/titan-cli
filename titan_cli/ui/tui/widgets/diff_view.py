"""
`DiffView`: one file's diff as code - line-number gutter, a coloured bar, a tinted background
across the whole line for what was added or removed, and syntax highlighting by file extension.

It is a catalog widget registered as `titan.diff`; a tree draws it with `Diff(diff)` from
`titan_cli.ui.elements`. `diff` is any object shaped like `titan_plugin_git`'s `UIFileDiff`
(`path`, `is_binary`, `hunks` of `header` and `lines` of `kind`/`text`/`old_no`/`new_no`), so
Titan itself depends on no plugin. It never wraps: a line wider than the widget scrolls sideways (the scrollbar under the
code, or shift + wheel), and the screen holding it scrolls vertically. `render_diff` is the pure
part, for tests.
"""
from typing import Any, List, Optional, Tuple

from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text as RichText
from textual.containers import HorizontalScroll
from textual.widgets import Static

from titan_cli.ui.elements import DIFF_COMPONENT, DiffProps
from titan_cli.ui.tui import colors
from titan_cli.ui.tui.widgets.registry import register_widget

_ADD_BG = "#16301f"
_DEL_BG = "#35161b"
_HEADER_BG = colors.SURFACE_LIGHTEN_1
_BAR = {"add": colors.SUCCESS, "del": colors.ERROR}
_BG = {"add": _ADD_BG, "del": _DEL_BG}
_MARK = {"add": "+", "del": "-"}
_TAB = 4


def _lexer(path: str) -> Optional[Any]:
    """The pygments lexer for a file name, None when it has no known language."""
    from pygments.lexers import get_lexer_for_filename
    from pygments.util import ClassNotFound

    try:
        return get_lexer_for_filename(path, stripnl=False)
    except ClassNotFound:
        return None


def _foreground_only(style: Any) -> Style:
    """A token's own colour and weight; its background is the line's, not the theme's."""
    if isinstance(style, str):
        style = Style.parse(style)
    return Style(color=style.color, bold=style.bold, italic=style.italic, underline=style.underline)


def _highlight(texts: List[str], path: str) -> List[RichText]:
    """Each code line as Rich text with syntax colours; plain when the language is unknown."""
    plain = [RichText(t.expandtabs(_TAB), no_wrap=True) for t in texts]
    lexer = _lexer(path)
    if lexer is None or not texts:
        return plain
    try:
        code = "\n".join(t.expandtabs(_TAB) for t in texts)
        highlighted = Syntax(code, lexer, theme="dracula").highlight(code)
        highlighted.spans = [
            type(span)(span.start, span.end, _foreground_only(span.style)) for span in highlighted.spans
        ]
        lines = list(highlighted.split("\n", allow_blank=True))
    except Exception:
        return plain
    # Pygments ends the code with a newline of its own: an empty line past the last one.
    if len(lines) == len(texts) + 1 and not lines[-1].plain:
        lines.pop()
    if len(lines) != len(texts):
        return plain
    for line in lines:
        line.style = Style()  # the theme's background, which the diff line replaces
        line.no_wrap = True
    return lines


def _note(text: str) -> RichText:
    return RichText(text, style=Style(color=colors.TEXT_MUTED, dim=True), no_wrap=True)


def _digits(diff: Any) -> int:
    numbers = [n for h in diff.hunks for line in h.lines for n in (line.old_no, line.new_no) if n]
    return len(str(max(numbers))) if numbers else 1


def _pad(row: RichText, width: int, bg: Optional[str]) -> RichText:
    """Fill a tinted line up to `width` so its background reaches the edge."""
    if bg:
        row.append(" " * max(0, width - row.cell_len))
        row.stylize(Style(bgcolor=bg))
    return row


def render_diff(diff: Any, width: int, max_lines: int) -> RichText:
    """
    The whole diff as one Rich text, at most `max_lines` lines of code. Tinted lines are as wide
    as the widest line or `width`, whichever is more; nothing is cut.
    """
    return layout_diff(diff, width, max_lines)[0]


def layout_diff(diff: Any, width: int, max_lines: int) -> Tuple[RichText, int]:
    """`render_diff` and the width its tinted lines were filled to: what a scrolling box needs."""
    if diff.is_binary:
        return _note("Binary file not shown"), 0
    if not diff.hunks:
        return _note("No changes to show"), 0
    digits = _digits(diff)
    two_columns = any(line.kind != "add" for h in diff.hunks for line in h.lines)
    out: List[Tuple[RichText, Optional[str]]] = []
    shown = 0
    for hunk in diff.hunks:
        if shown >= max_lines:
            break
        out.append((RichText(f"  {hunk.header}", style=Style(color=colors.INFO, dim=True), no_wrap=True), _HEADER_BG))
        lines = hunk.lines[: max_lines - shown]
        code = [line for line in lines if line.kind != "no_newline"]
        highlighted = iter(_highlight([line.text for line in code], diff.path))
        for line in lines:
            shown += 1
            if line.kind == "no_newline":
                out.append((RichText(f"  {'':>{digits}} \\ {line.text}", style=Style(color=colors.TEXT_MUTED, dim=True), no_wrap=True), None))
                continue
            row = RichText(no_wrap=True)
            row.append("▌" if line.kind in _BAR else " ", style=Style(color=_BAR.get(line.kind)))
            gutter = f"{line.old_no or '':>{digits}} " if two_columns else ""
            gutter += f"{line.new_no or '':>{digits}}"
            row.append(f" {gutter} ", style=Style(color=colors.TEXT_MUTED, dim=True))
            row.append(f"{_MARK.get(line.kind, ' ')} ", style=Style(color=_BAR.get(line.kind)))
            row.append_text(next(highlighted))
            out.append((row, _BG.get(line.kind)))
    hidden = sum(len(h.lines) for h in diff.hunks) - shown
    if hidden > 0:
        out.append((_note(f"  … {hidden} more lines"), None))
    full = max([width] + [row.cell_len for row, _ in out])
    return RichText("\n").join(_pad(row, full, bg) for row, bg in out), full


class DiffView(HorizontalScroll):
    """Draws a `DiffProps` with `layout_diff`, again when its width changes, scrolling sideways."""

    DEFAULT_CSS = """
    DiffView {
        height: auto;
        width: 1fr;
    }
    DiffView > Static {
        height: auto;
    }
    """

    def __init__(self, props: DiffProps):
        super().__init__()
        self._props = props
        self._body = Static("")
        self._painted_width = 0

    def compose(self):
        yield self._body

    def apply(self, props: DiffProps) -> None:
        if props != self._props:
            self._props = props
            self._paint()

    def on_mount(self) -> None:
        self._paint()

    def on_resize(self, event) -> None:
        if event.size.width != self._painted_width:
            self._paint()

    def _paint(self) -> None:
        self._painted_width = self.size.width
        text, full = layout_diff(self._props.diff, self._painted_width or 80, self._props.max_lines)
        self._body.styles.width = max(full, 1) if full else "1fr"
        self._body.update(text)


register_widget(DIFF_COMPONENT, DiffView)
