"""
List Detail Panel Widget

The two-pane layout of the Plugins and Mods screens: a selectable list on the left
(one roomy row per item) and a scrollable details pane on the right.
"""

from typing import Optional, Sequence

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widget import Widget
from textual.widgets import OptionList


class ListDetailPanel(Container):
    """
    A bordered list beside a bordered details pane.

    Usage:
        ListDetailPanel(
            "Installed Plugins", "Plugin Details",
            list_id="plugin-list", scroll_id="plugin-details", content_id="details-content",
            left_footer=[Button("Install")],
        )

    The screen fills the list (``OptionList`` with ``list_id``) and mounts what it wants
    shown into the ``Container`` with ``content_id``, replacing it on each selection.
    ``left_footer`` widgets sit under the list; ``list_width`` is the list's share of the
    width, in percent.
    """

    DEFAULT_CSS = """
    ListDetailPanel {
        width: 100%;
        height: 1fr;
        background: $surface-lighten-1;
    }

    ListDetailPanel > Horizontal {
        width: 100%;
        height: 1fr;
        padding: 1;
    }

    ListDetailPanel .list-detail-left {
        width: 20%;
        height: 100%;
        border: round $primary;
        border-title-align: center;
        background: $surface-lighten-1;
        padding: 0;
    }

    ListDetailPanel .list-detail-left OptionList {
        height: 1fr;
        width: 100%;
        padding: 1;
    }

    ListDetailPanel .list-detail-left OptionList > .option-list--option {
        padding: 1;
    }

    ListDetailPanel .list-detail-right {
        width: 80%;
        height: 1fr;
        border: round $primary;
        border-title-align: center;
        background: $surface-lighten-1;
        padding: 0;
    }

    ListDetailPanel .list-detail-scroll {
        height: 100%;
        width: 100%;
        padding: 1;
    }

    ListDetailPanel .list-detail-content {
        height: auto;
        width: 100%;
    }
    """

    def __init__(
        self,
        list_title: str,
        details_title: str,
        *,
        list_id: str,
        scroll_id: str,
        content_id: str,
        left_footer: Optional[Sequence[Widget]] = None,
        list_width: int = 20,
        id: Optional[str] = None,
    ) -> None:
        super().__init__(id=id)
        self._list_title = list_title
        self._details_title = details_title
        self._list_id = list_id
        self._scroll_id = scroll_id
        self._content_id = content_id
        self._left_footer = list(left_footer or [])
        self._list_width = list_width

    def compose(self) -> ComposeResult:
        with Horizontal():
            left = Container(classes="list-detail-left")
            left.border_title = self._list_title
            left.styles.width = f"{self._list_width}%"
            with left:
                yield OptionList(id=self._list_id)
                for widget in self._left_footer:
                    yield widget
            right = Container(classes="list-detail-right")
            right.border_title = self._details_title
            right.styles.width = f"{100 - self._list_width}%"
            with right:
                with VerticalScroll(id=self._scroll_id, classes="list-detail-scroll"):
                    yield Container(id=self._content_id, classes="list-detail-content")
