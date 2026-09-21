"""Collapsible, width-friendly rendering for structured JSON values."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget

from titan_cli.messages import msg
from titan_cli.ui.tui.colors import RichStyles

from .collapsible_list import CollapsibleEntry, build_collapsible_list


# Fields that make an object recognizable when it appears inside a list. Without
# one of these, a large array is presented as an anonymous run of indices.
NAME_FIELDS = (
    "name",
    "title",
    "label",
    "displayName",
    "id",
    "code",
    "type",
    "item_name",
    "screen_name",
    "promotion_name",
    "item_id",
)

# Tiny scalar-only objects are clearer inline. Objects containing another
# collection always become their own collapsible node.
INLINE_FIELDS = 3


@dataclass(frozen=True)
class JsonTreeDetail:
    """One structured JSON block to render as a tree."""

    title: str
    value: Any
    collapsed: bool = True


class JsonTree(Widget):
    """Render JSON as aligned scalar fields and collapsible nested nodes."""

    DEFAULT_CSS = """
    JsonTree {
        width: 100%;
        height: auto;
        margin: 1 0 0 2;
    }

    JsonTree > .json-tree {
        width: 100%;
        height: auto;
    }
    """

    def __init__(
        self,
        title: str,
        value: Any,
        *,
        collapsed: bool = True,
        max_scalar_length: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the JSON tree."""
        super().__init__(**kwargs)
        self.title = title
        self.value = value
        self.collapsed = collapsed
        self.max_scalar_length = max_scalar_length

    def compose(self) -> ComposeResult:
        """Compose the value using Titan's shared collapsible rows."""
        entry = build_json_entry(
            self.title,
            self.value,
            expanded=not self.collapsed,
            max_scalar_length=self.max_scalar_length,
        )
        yield build_collapsible_list([entry], classes="json-tree")


def build_json_entry(
    title: str,
    value: Any,
    *,
    expanded: bool = False,
    key_width: int = 24,
    max_scalar_length: int | None = None,
    copy_label: str | None = None,
) -> CollapsibleEntry:
    """Build one reusable collapsible entry for a JSON-like value."""
    inline, children = _build_json_value(
        value,
        key_width=key_width,
        max_scalar_length=max_scalar_length,
    )
    return CollapsibleEntry(
        title=title,
        body=[inline] if inline is not None else [],
        children=children,
        expanded=expanded,
        copy_text=_serialize(value),
        copy_label=copy_label or title,
    )


def _build_json_value(
    value: Any,
    *,
    key_width: int = 24,
    max_scalar_length: int | None = None,
) -> tuple[Text | None, list[CollapsibleEntry]]:
    """Split a value into visible scalar fields and nested foldable entries."""
    if isinstance(value, list):
        if not value:
            return Text("[]", style=RichStyles.DIM), []
        return None, [
            _item_entry(index, item, key_width, max_scalar_length)
            for index, item in enumerate(value)
        ]

    if not isinstance(value, dict):
        return _scalar_text(value, max_scalar_length), []

    scalars: list[tuple[str, Any]] = []
    entries: list[CollapsibleEntry] = []
    for key, item in value.items():
        if _is_inline(item):
            scalars.append((str(key), item))
        else:
            entries.append(
                _nested_entry(str(key), item, key_width, max_scalar_length)
            )

    return _aligned(scalars, key_width, max_scalar_length), entries


def _is_inline(value: Any) -> bool:
    if isinstance(value, list):
        return not value
    if isinstance(value, dict):
        return len(value) <= INLINE_FIELDS and all(
            not isinstance(item, (dict, list)) for item in value.values()
        )
    return True


def _nested_entry(
    key: str,
    value: Any,
    key_width: int,
    max_scalar_length: int | None,
) -> CollapsibleEntry:
    if isinstance(value, list):
        count = len(value)
        count_label = (
            msg.StructuredData.ITEM_COUNT
            if count == 1
            else msg.StructuredData.ITEM_COUNT_PLURAL
        ).format(count=count)
        return CollapsibleEntry(
            title=_title(key, count_label),
            children=[
                _item_entry(index, item, key_width, max_scalar_length)
                for index, item in enumerate(value)
            ],
            copy_text=_serialize(value),
            copy_label=key,
        )

    inline, children = _build_json_value(
        value,
        key_width=key_width,
        max_scalar_length=max_scalar_length,
    )
    return CollapsibleEntry(
        title=_title(key, _identify(value)),
        body=[inline] if inline is not None else [],
        children=children,
        copy_text=_serialize(value),
        copy_label=key,
    )


def _item_entry(
    index: int,
    item: Any,
    key_width: int,
    max_scalar_length: int | None,
) -> CollapsibleEntry:
    if not isinstance(item, (dict, list)):
        rendered = _format_scalar(item, max_scalar_length)
        return CollapsibleEntry(
            title=_title(str(index), rendered),
            copy_text=_serialize(item),
            copy_label=str(index),
        )

    inline, children = _build_json_value(
        item,
        key_width=key_width,
        max_scalar_length=max_scalar_length,
    )
    identifier = _identify(item) if isinstance(item, dict) else ""
    return CollapsibleEntry(
        title=_title(str(index), identifier),
        body=[inline] if inline is not None else [],
        children=children,
        copy_text=_serialize(item),
        copy_label=identifier or str(index),
    )


def _identify(value: dict[Any, Any]) -> str:
    """Return the first scalar field that distinguishes an object in a list."""
    for field in NAME_FIELDS:
        item = value.get(field)
        if item is not None and not isinstance(item, (dict, list)):
            return _format_scalar(item, None)
    return ""


def _title(name: str, detail: str) -> str:
    return f"{name}   {detail}".rstrip() if detail else name


def _aligned(
    pairs: list[tuple[str, Any]],
    key_width: int,
    max_scalar_length: int | None,
) -> Text | None:
    if not pairs:
        return None

    width = min(max(len(key) for key, _ in pairs), key_width)
    output = Text()
    for index, (key, value) in enumerate(pairs):
        output.append(key.ljust(width), style=f"bold {RichStyles.TEXT}")
        output.append(
            "  " + _format_inline(value, max_scalar_length),
            style=_value_style(value),
        )
        if index < len(pairs) - 1:
            output.append("\n")
    return output


def _scalar_text(value: Any, max_scalar_length: int | None) -> Text:
    return Text(
        _format_scalar(value, max_scalar_length),
        style=_value_style(value),
    )


def _format_inline(value: Any, max_scalar_length: int | None) -> str:
    if isinstance(value, (dict, list)):
        rendered = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
        return _truncate(rendered, max_scalar_length)
    return _format_scalar(value, max_scalar_length)


def _format_scalar(value: Any, max_scalar_length: int | None) -> str:
    if isinstance(value, str):
        rendered = value
    elif value is None:
        rendered = "null"
    elif isinstance(value, bool):
        rendered = "true" if value else "false"
    else:
        rendered = str(value)
    return _truncate(rendered, max_scalar_length)


def _truncate(value: str, max_length: int | None) -> str:
    if max_length is None or len(value) <= max_length:
        return value
    if max_length <= 1:
        return value[:max_length]
    return f"{value[: max_length - 1]}…"


def _value_style(value: Any) -> str:
    if isinstance(value, (dict, list)) and not value:
        return RichStyles.DIM
    if value is None or isinstance(value, (bool, int, float)):
        return RichStyles.INFO
    return RichStyles.TEXT


def _serialize(value: Any) -> str:
    """Return stable, readable JSON for the copy affordance."""
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return ""
