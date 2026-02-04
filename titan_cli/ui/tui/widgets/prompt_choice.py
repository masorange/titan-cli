"""
PromptChoice Widget

Widget for selecting a single option from multiple choices using buttons.
"""

from typing import Callable, List, Any
from dataclasses import dataclass
from textual.widget import Widget
from textual.containers import Horizontal
from .text import BoldText, DimText
from .button import Button


@dataclass
class ChoiceOption:
    """
    Option for choice selection.

    Attributes:
        value: The value to return when selected (can be any type)
        label: The text to display on the button
        variant: Button variant (default, primary, success, warning, error)
    """
    value: Any
    label: str
    variant: str = "default"


class PromptChoice(Widget):
    """
    Widget for selecting a single option from multiple choices.

    Displays a question and horizontal buttons for each option.
    User clicks a button to select that option.

    Example:
        options = [
            ChoiceOption(value="use", label="Use as-is", variant="primary"),
            ChoiceOption(value="edit", label="Edit", variant="default"),
            ChoiceOption(value="reject", label="Reject", variant="error"),
        ]

        choice_widget = PromptChoice(
            question="What would you like to do?",
            options=options,
            on_select=lambda value: print(f"Selected: {value}")
        )
    """

    # Allow this widget to receive focus
    can_focus = True
    can_focus_children = True

    DEFAULT_CSS = """
    PromptChoice {
        width: 100%;
        height: auto;
        padding: 1;
        margin: 1 0;
        background: $surface-lighten-1;
        border: round $accent;
    }

    PromptChoice > BoldText,
    PromptChoice > DimText {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    PromptChoice Horizontal {
        width: 100%;
        height: auto;
        align: center middle;
    }

    PromptChoice Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        question: str,
        options: List[ChoiceOption],
        on_select: Callable[[Any], None],
        **kwargs
    ):
        """
        Initialize PromptChoice.

        Args:
            question: Question to display above the buttons
            options: List of ChoiceOption instances
            on_select: Callback that receives the selected value
        """
        super().__init__(**kwargs)
        self.question = question
        self.options = options
        self.on_select_callback = on_select

    def compose(self):
        # Question text
        yield BoldText(self.question)

        # Instructions
        yield DimText("Select an option:")

        # Buttons in horizontal layout
        with Horizontal():
            for i, option in enumerate(self.options):
                button = Button(
                    option.label,
                    variant=option.variant,
                    id=f"choice-btn-{i}"
                )
                button.choice_value = option.value  # Store value on button
                yield button

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press - call callback with selected value."""
        if hasattr(event.button, 'choice_value'):
            self.on_select_callback(event.button.choice_value)
            event.stop()

    def on_mount(self):
        """Focus first button when mounted."""
        self.call_after_refresh(self._focus_first_button)

    def _focus_first_button(self):
        """Focus the first button."""
        try:
            first_button = self.query_one("#choice-btn-0", Button)
            self.app.set_focus(first_button)
            self.scroll_visible(animate=False)
        except Exception:
            pass
