"""
The contract of a widget that can be redrawn in place.

A widget built from a description (an element, props) implements `apply(props)`: it takes the
new description and brings itself in line without being remounted, so nothing flashes and the
user's focus, cursor and typed text survive a repaint. `kind(props)` of the registry says which
widget class a description needs; a mounted widget of another class is replaced, not applied.
"""
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Updatable(Protocol):
    def apply(self, props: Any) -> None:
        """Take `props` as the new description. Keep state that is the user's (focus, typed text)."""
