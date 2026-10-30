"""
Elements' text as Rich text, and `Line`, the one-row widget that shows it.

Colors are the semantic names of `titan_cli.ui.elements` mapped onto the theme; a `Link` is a
span that runs the `open_link` action of the line holding it, which opens only web addresses.
"""
import re
from typing import Any

from rich.style import Style
from rich.text import Text as RichText
from textual.widgets import Static

from titan_cli.core.logging import get_logger
from titan_cli.ui.elements import Link, Text
from titan_cli.ui.tui import colors

logger = get_logger(__name__)

COLORS = {
    "primary": colors.PRIMARY,
    "accent": colors.ACCENT,
    "success": colors.SUCCESS,
    "warning": colors.WARNING,
    "error": colors.ERROR,
    "info": colors.INFO,
    "subtle": colors.TEXT_MUTED,
}


def _color(name: Any) -> Any:
    return COLORS.get(name, name) if name else None


def to_rich(text: Text, inherited: Style = Style()) -> RichText:
    """Flatten a `Text` element, nested spans included, into one Rich Text."""
    style = inherited + Style(
        color=_color(text.color), bold=text.bold or None, dim=text.dim or None
    )
    out = RichText(no_wrap=not text.wrap, overflow="fold" if text.wrap else "ellipsis")
    for part in text.parts:
        if isinstance(part, Text):
            out.append_text(to_rich(part, style))
        elif isinstance(part, Link):
            out.append_text(link_text(part, style))
        else:
            out.append_text(with_urls(str(part), style))
    return out


def _link_style(url: str, inherited: Style) -> Style:
    return inherited + Style(color=_color("info"), underline=True) + Style.from_meta({"@click": f"open_link({url!r})"})


def link_text(link: Link, inherited: Style = Style()) -> RichText:
    """A link's label, underlined; a click runs the `open_link` action of the line holding it."""
    return RichText(link.label, style=_link_style(link.url, inherited))


_URL = re.compile(r"https?://[^\s<>\"'`]+")


def with_urls(text: str, style: Style = Style()) -> RichText:
    """
    Plain text whose web addresses are links. Every piece of a wrapped address carries
    the whole URL, so a click on any of its lines opens all of it - left to the terminal,
    only the part on the clicked line would open.
    """
    out = RichText()
    at = 0
    for match in _URL.finditer(text):
        url = match.group().rstrip(".,;:!?")
        if url.endswith(")") and "(" not in url:
            url = url[:-1]
        out.append(text[at:match.start()], style)
        out.append(url, _link_style(url, style))
        at = match.start() + len(url)
    out.append(text[at:], style)
    return out


class Line(Static):
    DEFAULT_CSS = """
    Line {
        height: auto;
        width: 1fr;
    }
    """

    def action_open_link(self, url: str) -> None:
        # A mod's URL: only the web, never file:// or a custom scheme handler.
        if not url.startswith(("https://", "http://")):
            logger.warning("mod_link_refused", url=url)
            return
        self.app.open_url(url)
