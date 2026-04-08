"""
Development source path modal.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Input

from .button import Button
from .text import BoldPrimaryText, DimText


class DevSourcePathModal(ModalScreen[str | None]):
    """Simple modal for capturing a local development path."""

    CSS = """
    DevSourcePathModal {
        align: center middle;
    }

    #dev-source-dialog {
        width: 80;
        height: auto;
        border: round $primary;
        background: $surface-lighten-1;
        padding: 1 2;
    }

    #dev-source-dialog Input {
        width: 100%;
        margin-top: 1;
    }

    #dev-source-buttons {
        width: 100%;
        height: auto;
        align: right middle;
        margin-top: 1;
    }
    """

    def __init__(self, plugin_name: str, initial_value: str = "", **kwargs):
        super().__init__(**kwargs)
        self.plugin_name = plugin_name
        self.initial_value = initial_value

    def compose(self) -> ComposeResult:
        with Container(id="dev-source-dialog"):
            yield BoldPrimaryText(f"Development Source: {self.plugin_name}")
            yield DimText("Enter the local repository path for this plugin.")
            yield Input(
                value=self.initial_value,
                placeholder="/path/to/plugin-repo",
                id="dev-source-input",
            )
            with Horizontal(id="dev-source-buttons"):
                yield Button("Cancel", variant="default", id="cancel-dev-source-button")
                yield Button("Save", variant="primary", id="save-dev-source-button")

    def on_mount(self) -> None:
        self.query_one("#dev-source-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-dev-source-button":
            self.dismiss(None)
        elif event.button.id == "save-dev-source-button":
            value = self.query_one("#dev-source-input", Input).value.strip()
            self.dismiss(value or None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "dev-source-input":
            self.dismiss(event.value.strip() or None)
