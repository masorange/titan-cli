"""Expandable list widgets for compact detail-heavy output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from textual.app import ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import Collapsible, Static

from titan_cli.ui.tui.widgets.json_tree import JsonTree, JsonTreeDetail
from titan_cli.ui.tui.widgets.table import Table


@dataclass(frozen=True)
class ExpandableListItem:
    """One item in an expandable list."""

    title: str
    subtitle: str = ""
    badge: str = ""
    summary: str = ""
    detail_headers: Sequence[str] = field(default_factory=tuple)
    detail_rows: Sequence[Sequence[str]] = field(default_factory=tuple)
    detail_flex_column: int | None = None
    json_details: Sequence[JsonTreeDetail] = field(default_factory=tuple)
    collapsed: bool = True

    @property
    def header(self) -> str:
        """Compact title shown while the item is collapsed."""
        parts = [self.title]
        if self.badge:
            parts.append(f"[{self.badge}]")
        if self.summary:
            parts.append(self.summary)
        return "  ".join(parts)


class ExpandableList(Widget):
    """A stack of collapsible rows with optional detail tables."""

    DEFAULT_CSS = """
    ExpandableList {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
    }

    ExpandableList > Container {
        width: 100%;
        height: auto;
        border: round $primary;
        padding: 1;
    }

    ExpandableList .expandable-list-title {
        width: 100%;
        height: auto;
        color: $success;
        text-style: bold;
        margin: 0 0 1 0;
    }

    ExpandableList Collapsible {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
    }

    ExpandableList CollapsibleTitle {
        width: 100%;
        height: auto;
        background: $surface-lighten-1;
        color: $text;
        text-style: bold;
    }

    ExpandableList .expandable-list-subtitle {
        width: 100%;
        height: auto;
        color: $text-muted;
        margin: 0 0 1 2;
    }

    ExpandableList DataTable {
        width: 100%;
        height: auto;
        margin: 0 0 0 2;
    }
    """

    def __init__(
        self,
        items: Iterable[ExpandableListItem],
        *,
        title: str = "",
        detail_cell_padding: int = 1,
        **kwargs,
    ) -> None:
        """Initialize the expandable list."""
        super().__init__(**kwargs)
        self.items = list(items)
        self.title_text = title
        self.detail_cell_padding = detail_cell_padding

    def compose(self) -> ComposeResult:
        """Compose the list."""
        with Container():
            if self.title_text:
                yield Static(self.title_text, classes="expandable-list-title")
            for item in self.items:
                yield self._collapsible_item(item)

    def _collapsible_item(self, item: ExpandableListItem) -> Collapsible:
        """Build one collapsible row."""
        children = []
        if item.subtitle:
            children.append(Static(item.subtitle, classes="expandable-list-subtitle"))
        has_details = False
        if item.detail_rows:
            has_details = True
            children.append(
                Table(
                    headers=list(item.detail_headers),
                    rows=[list(row) for row in item.detail_rows],
                    cell_padding=self.detail_cell_padding,
                    zebra_stripes=True,
                    show_cursor=False,
                    flex_column=item.detail_flex_column,
                )
            )
        for detail in item.json_details:
            has_details = True
            children.append(
                JsonTree(
                    detail.title,
                    detail.value,
                    collapsed=detail.collapsed,
                )
            )
        if not has_details:
            children.append(Static("Sin detalles", classes="expandable-list-subtitle"))
        return Collapsible(
            *children,
            title=item.header,
            collapsed=item.collapsed,
        )
