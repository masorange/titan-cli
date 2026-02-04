"""
PromptSelectionList Widget

Widget wrapper for SelectionList that handles multi-selection with checkboxes.
"""

from typing import Callable, List, Any
from dataclasses import dataclass
from textual.widget import Widget
from textual.widgets import SelectionList
from textual.widgets.selection_list import Selection
from .text import BoldText, DimText


@dataclass
class SelectionOption:
    """
    Option for selection list.

    Attributes:
        value: The value to return when selected (can be any type)
        label: The text to display in the list
        selected: Whether the option is initially selected
    """
    value: Any
    label: str
    selected: bool = False


class PromptSelectionList(Widget):
    """
    Widget wrapper for SelectionList that handles multi-selection events.

    Displays a question and a list of options with checkboxes that the user
    can toggle with Space and confirm with Enter.
    """

    # Allow this widget and its children to receive focus
    can_focus = True
    can_focus_children = True

    DEFAULT_CSS = """
    PromptSelectionList {
        width: 100%;
        height: auto;
        padding: 1;
        margin: 1 0;
        background: $surface-lighten-1;
        border: round $accent;
    }

    PromptSelectionList > BoldText,
    PromptSelectionList > DimText {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    PromptSelectionList > SelectionList {
        width: 100%;
        height: auto;
        max-height: 20;
    }

    PromptSelectionList .selection-list--option {
        padding: 0 1;
    }

    PromptSelectionList .selection-list--option-highlighted {
        background: $accent 20%;
    }
    """

    def __init__(
        self,
        question: str,
        options: List[SelectionOption],
        on_submit: Callable[[List[Any]], None],
        **kwargs
    ):
        """
        Initialize PromptSelectionList.

        Args:
            question: Question to display above the selection list
            options: List of SelectionOption instances
            on_submit: Callback that receives list of selected values
        """
        super().__init__(**kwargs)
        self.question = question
        self.options = options
        self.on_submit_callback = on_submit

    def compose(self):
        # Question text
        yield BoldText(self.question)

        # Instructions
        yield DimText("↑/↓: Navegar  │  Space: Seleccionar/Deseleccionar  │  Enter: Continuar")

        # Create Selection objects for SelectionList
        selections = [
            Selection(
                value=str(i),  # Use index as internal value
                prompt=option.label,
                initial_state=option.selected
            )
            for i, option in enumerate(self.options)
        ]

        # SelectionList widget
        yield SelectionList(*selections, id="selection-list")

    def on_mount(self):
        """Focus selection list when mounted and scroll into view."""
        self.call_after_refresh(self._focus_list)

    def _focus_list(self):
        """Focus the selection list widget and scroll into view."""
        try:
            selection_list = self.query_one(SelectionList)
            # Use app.set_focus() to force focus change
            self.app.set_focus(selection_list)
            # Scroll to make this widget visible
            self.scroll_visible(animate=False)
        except Exception:
            pass

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        """Handle when user presses Enter to confirm selection."""
        # Don't handle automatically - wait for explicit submission
        pass

    async def on_key(self, event) -> None:
        """Intercept Enter key before it reaches SelectionList."""
        if event.key == "enter":
            # Stop propagation FIRST to prevent SelectionList from handling it
            event.stop()
            event.prevent_default()

            try:
                selection_list = self.query_one(SelectionList)
                # Get indices of selected items
                selected_indices = [int(sel) for sel in selection_list.selected]
                # Map indices back to option values
                selected_values = [self.options[i].value for i in selected_indices]
                # Call the callback with selected values
                self.on_submit_callback(selected_values)
            except Exception:
                pass
