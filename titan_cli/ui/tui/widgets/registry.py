"""
Registry of widgets that elements can name: `Component(name, props)` in a tree is drawn by the
widget registered under `name`.

A mod or workspace registers its own `Updatable` widget in its `register()` and uses it like a
catalog one; the author accepts the Textual coupling. Names are global, so prefix them with
the mod's or workspace's own (`"git.graph"`). Registering a name again replaces it, which is
what reloading a mod does.
"""
from typing import Dict, Optional

from titan_cli.core.logging import get_logger
from titan_cli.ui.tui.widgets.updatable import Updatable

logger = get_logger(__name__)

_WIDGETS: Dict[str, type] = {}


def register_widget(name: str, widget: type) -> None:
    """Make `Component(name, props)` draw `widget(props)`; `widget` must be `Updatable`."""
    if not (isinstance(widget, type) and issubclass(widget, Updatable)):
        raise TypeError(f"widget {name!r}: {widget!r} must be a class with apply(props)")
    if name in _WIDGETS and _WIDGETS[name] is not widget:
        logger.info("widget_replaced", name=name)
    _WIDGETS[name] = widget


def unregister_widget(name: str) -> None:
    _WIDGETS.pop(name, None)


def widget_for(name: str) -> Optional[type]:
    return _WIDGETS.get(name)
