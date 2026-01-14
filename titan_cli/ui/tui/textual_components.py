"""
Textual UI Components container for workflow context.

Provides utilities for workflow steps to mount widgets and request user input in the TUI.

Steps can import widgets directly from titan_cli.ui.tui.widgets and mount them using ctx.textual.
"""

import threading
from typing import Optional
from textual.widget import Widget


class TextualComponents:
    """
    Textual UI utilities for workflow steps.

    Steps import widgets directly (Panel, DimText, etc.) and use these utilities to:
    - Mount widgets to the output panel
    - Append simple text with markup
    - Request user input interactively

    Example:
        from titan_cli.ui.tui.widgets import Panel, DimText

        def my_step(ctx):
            # Mount a panel widget
            ctx.textual.mount(Panel("Warning message", panel_type="warning"))

            # Append inline text
            ctx.textual.text("Analyzing changes...")

            # Ask for input
            response = ctx.textual.ask_confirm("Continue?", default=True)
    """

    def __init__(self, app, output_widget):
        """
        Initialize Textual components.

        Args:
            app: TitanApp instance for thread synchronization
            output_widget: WorkflowExecutionContent widget to render to
        """
        self.app = app
        self.output_widget = output_widget

    def mount(self, widget: Widget) -> None:
        """
        Mount a widget to the output panel.

        Args:
            widget: Any Textual widget to mount (Panel, DimText, etc.)

        Example:
            from titan_cli.ui.tui.widgets import Panel
            ctx.textual.mount(Panel("Success!", panel_type="success"))
        """
        def _mount():
            self.output_widget.mount(widget)
        # Call from thread since executor runs in background thread
        self.app.call_from_thread(_mount)

    def text(self, text: str, markup: str = "") -> None:
        """
        Append inline text with optional Rich markup.

        Args:
            text: Text to append
            markup: Optional Rich markup style (e.g., "cyan", "bold green")

        Example:
            ctx.textual.text("Analyzing changes...", markup="cyan")
            ctx.textual.text("Done!")
        """
        def _append():
            if markup:
                self.output_widget.append_output(f"[{markup}]{text}[/{markup}]")
            else:
                self.output_widget.append_output(text)
        # Call from thread since executor runs in background thread
        self.app.call_from_thread(_append)

    def ask_text(self, question: str, default: str = "") -> Optional[str]:
        """
        Ask user for text input (blocks until user responds).

        Args:
            question: Question to ask
            default: Default value

        Returns:
            User's input text, or None if empty

        Example:
            message = ctx.textual.ask_text("Enter commit message:", default="")
        """
        from textual.widgets import Input

        # Event and result container for synchronization
        result_event = threading.Event()
        result_container = {"value": None}

        def _mount_input():
            # Show question
            self.output_widget.append_output(f"[bold cyan]{question}[/bold cyan]")

            # Create Input widget
            input_widget = Input(
                value=default,
                placeholder="Type here and press Enter...",
                id=f"prompt-input-{id(result_event)}"
            )

            # Handler when Enter is pressed
            def on_submitted(event):
                value = event.value
                result_container["value"] = value

                # Show what user entered (confirmation)
                self.output_widget.append_output(f"  → {value}")

                # Remove the input widget
                input_widget.remove()

                # Unblock the step
                result_event.set()

            # Connect event handler
            input_widget.on(Input.Submitted, on_submitted)

            # Mount and focus
            self.output_widget.mount(input_widget)
            input_widget.focus()

        # Call from thread since executor runs in background thread
        self.app.call_from_thread(_mount_input)

        # BLOCK here until user responds
        result_event.wait()

        return result_container["value"]

    def ask_confirm(self, question: str, default: bool = True) -> bool:
        """
        Ask user for confirmation (Y/N).

        Args:
            question: Question to ask
            default: Default value (True = Y, False = N)

        Returns:
            True if user confirmed, False otherwise

        Example:
            if ctx.textual.ask_confirm("Use AI message?", default=True):
                # User said yes
        """
        default_hint = "Y/n" if default else "y/N"
        response = self.ask_text(f"{question} ({default_hint})", default="")

        # Parse response
        if response is None or response.strip() == "":
            return default

        response_lower = response.strip().lower()
        if response_lower in ["y", "yes"]:
            return True
        elif response_lower in ["n", "no"]:
            return False
        else:
            # Invalid response, use default
            return default
