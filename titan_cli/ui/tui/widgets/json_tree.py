"""JSON tree widgets for structured values in workflow output."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Tree
from textual.widgets._tree import TreeNode


@dataclass(frozen=True)
class JsonTreeDetail:
    """One structured JSON block to render as a tree."""

    title: str
    value: Any
    collapsed: bool = True


class JsonTree(Widget):
    """Render JSON-like data as collapsible object and array nodes."""

    DEFAULT_CSS = """
    JsonTree {
        width: 100%;
        height: auto;
        margin: 1 0 0 2;
    }

    JsonTree Tree {
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
        max_scalar_length: int = 72,
        **kwargs,
    ) -> None:
        """Initialize the JSON tree."""
        super().__init__(**kwargs)
        self.title = title
        self.value = value
        self.collapsed = collapsed
        self.max_scalar_length = max_scalar_length

    def compose(self) -> ComposeResult:
        """Compose the tree."""
        tree = Tree(f"{self.title} {_container_summary(self.value)}")
        tree.show_root = True
        self._add_children(tree.root, self.value)
        if not self.collapsed:
            tree.root.expand()
        yield tree

    def _add_children(self, node: TreeNode, value: Any) -> None:
        """Populate a tree node recursively."""
        if isinstance(value, dict):
            for key in sorted(value):
                child_value = value[key]
                label = str(key)
                if isinstance(child_value, (dict, list)):
                    child = node.add(f"{label}: {_container_summary(child_value)}")
                    self._add_children(child, child_value)
                else:
                    node.add_leaf(
                        f"{label}: {_format_scalar(child_value, self.max_scalar_length)}"
                    )
            return

        if isinstance(value, list):
            for index, child_value in enumerate(value):
                label = f"[{index}]"
                if isinstance(child_value, (dict, list)):
                    child = node.add(f"{label}: {_container_summary(child_value)}")
                    self._add_children(child, child_value)
                else:
                    node.add_leaf(
                        f"{label}: {_format_scalar(child_value, self.max_scalar_length)}"
                    )
            return

        node.add_leaf(_format_scalar(value, self.max_scalar_length))


def _container_summary(value: Any) -> str:
    """Describe a JSON container compactly."""
    if isinstance(value, dict):
        count = len(value)
        suffix = "clave" if count == 1 else "claves"
        return f"{{{count} {suffix}}}"
    if isinstance(value, list):
        count = len(value)
        suffix = "elemento" if count == 1 else "elementos"
        return f"[{count} {suffix}]"
    return ""


def _format_scalar(value: Any, max_length: int) -> str:
    """Render a scalar JSON value without allowing very long tree rows."""
    rendered = json.dumps(value, ensure_ascii=False)
    collapsed = " ".join(rendered.split())
    if len(collapsed) <= max_length:
        return collapsed
    if max_length <= 1:
        return collapsed[:max_length]
    return f"{collapsed[: max_length - 1]}…"
