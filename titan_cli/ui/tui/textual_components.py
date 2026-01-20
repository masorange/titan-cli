"""
Textual UI Components container for workflow context.

Provides utilities for workflow steps to mount widgets and request user input in the TUI.

Steps can import widgets directly from titan_cli.ui.tui.widgets and mount them using ctx.textual.
"""

import threading
from typing import Optional, Callable
from contextlib import contextmanager
from textual.widget import Widget
from textual.widgets import Input, LoadingIndicator, Static, Markdown, TextArea
from textual.containers import Container
from textual.message import Message


class PromptInput(Widget):
    """Widget wrapper for Input that handles submission events."""

    # Allow this widget and its children to receive focus
    can_focus = True
    can_focus_children = True

    DEFAULT_CSS = """
    PromptInput {
        width: 100%;
        height: auto;
        padding: 1;
        margin: 1 0;
        background: $surface-lighten-1;
        border: round $accent;
    }

    PromptInput > Static {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    PromptInput > Input {
        width: 100%;
    }
    """

    def __init__(self, question: str, default: str, placeholder: str, on_submit: Callable[[str], None], **kwargs):
        super().__init__(**kwargs)
        self.question = question
        self.default = default
        self.placeholder = placeholder
        self.on_submit_callback = on_submit

    def compose(self):
        from textual.widgets import Static
        yield Static(f"[bold cyan]{self.question}[/bold cyan]")
        yield Input(
            value=self.default,
            placeholder=self.placeholder,
            id="prompt-input"
        )

    def on_mount(self):
        """Focus input when mounted and scroll into view."""
        # Use call_after_refresh to ensure widget tree is ready
        self.call_after_refresh(self._focus_input)

    def _focus_input(self):
        """Focus the input widget and scroll into view."""
        try:
            input_widget = self.query_one(Input)
            # Use app.set_focus() to force focus change from steps-panel
            self.app.set_focus(input_widget)
            # Scroll to make this widget visible
            self.scroll_visible(animate=False)
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        value = event.value
        self.on_submit_callback(value)


class MultilineInput(TextArea):
    """Custom TextArea that handles Enter for submission and Shift+Enter for new lines."""

    class Submitted(Message):
        """Message sent when the input is submitted."""
        def __init__(self, sender: Widget, value: str):
            super().__init__()
            self.sender = sender
            self.value = value

    def _on_key(self, event) -> None:
        """Intercept key events before TextArea processes them."""
        from textual.events import Key

        # Check if it's Enter without shift
        if isinstance(event, Key) and event.key == "enter":
            # Submit the input
            self.post_message(self.Submitted(self, self.text))
            event.prevent_default()
            event.stop()
            return

        # For all other keys, let TextArea handle it
        super()._on_key(event)


class PromptTextArea(Widget):
    """Widget wrapper for MultilineInput that handles multiline input submission."""

    can_focus = True
    can_focus_children = True

    DEFAULT_CSS = """
    PromptTextArea {
        width: 100%;
        height: auto;
        padding: 1;
        margin: 1 0;
        background: $surface-lighten-1;
        border: round $accent;
    }

    PromptTextArea > Static {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    PromptTextArea > MultilineInput {
        width: 100%;
        height: auto;
    }

    PromptTextArea .hint-text {
        width: 100%;
        height: auto;
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self, question: str, default: str, on_submit: Callable[[str], None], **kwargs):
        super().__init__(**kwargs)
        self.question = question
        self.default = default
        self.on_submit_callback = on_submit

    def compose(self):
        from textual.widgets import Static
        yield Static(f"[bold cyan]{self.question}[/bold cyan]")
        yield MultilineInput(
            text=self.default,
            id="prompt-textarea",
            soft_wrap=True
        )
        yield Static("[dim]Press Enter to submit, Shift+Enter for new line[/dim]", classes="hint-text")

    def on_mount(self):
        """Focus textarea when mounted and scroll into view."""
        self.call_after_refresh(self._focus_textarea)

    def _focus_textarea(self):
        """Focus the textarea widget and scroll into view."""
        try:
            textarea = self.query_one(MultilineInput)
            self.app.set_focus(textarea)
            self.scroll_visible(animate=False)
        except Exception:
            pass

    def on_multiline_input_submitted(self, message: MultilineInput.Submitted):
        """Handle submission from MultilineInput."""
        self.on_submit_callback(message.value)


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

        # call_from_thread already blocks until the function completes
        try:
            self.app.call_from_thread(_mount)
        except Exception:
            # App is closing or worker was cancelled
            pass

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

        # call_from_thread already blocks until the function completes
        try:
            self.app.call_from_thread(_append)
        except Exception:
            # App is closing or worker was cancelled
            pass

    def markdown(self, markdown_text: str) -> None:
        """
        Render markdown content (parent container handles scrolling).

        Args:
            markdown_text: Markdown content to render

        Example:
            ctx.textual.markdown("## My Title\n\nSome **bold** text")
        """
        # Create markdown widget directly (Textual's Markdown already handles wrapping)
        md_widget = Markdown(markdown_text)

        # Apply basic styling - let it expand fully, parent has scroll
        md_widget.styles.width = "100%"
        md_widget.styles.height = "auto"
        md_widget.styles.padding = (1, 2)
        md_widget.styles.margin = (0, 0, 1, 0)

        def _mount():
            # Mount markdown to output
            self.output_widget.mount(md_widget)
            # Trigger autoscroll after mounting
            self.output_widget._scroll_to_end()

        # call_from_thread already blocks until the function completes
        try:
            self.app.call_from_thread(_mount)
        except Exception:
            # App is closing or worker was cancelled
            pass

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
        # Event and result container for synchronization
        result_event = threading.Event()
        result_container = {"value": None}

        def _mount_input():
            # Handler when Enter is pressed
            def on_submitted(value: str):
                result_container["value"] = value

                # Show what user entered (confirmation)
                self.output_widget.append_output(f"  → {value}")

                # Remove the input widget
                input_widget.remove()

                # Unblock the step
                result_event.set()

            # Create PromptInput widget that handles the submission
            input_widget = PromptInput(
                question=question,
                default=default,
                placeholder="Type here and press Enter...",
                on_submit=on_submitted
            )

            # Mount the widget (it will auto-focus)
            self.output_widget.mount(input_widget)

        # Call from thread since executor runs in background thread
        try:
            self.app.call_from_thread(_mount_input)
        except Exception:
            # App is closing or worker was cancelled
            return default

        # BLOCK here until user responds (with timeout to allow cancellation)
        # Wait in loop with timeout so we can be interrupted
        while not result_event.is_set():
            if result_event.wait(timeout=0.5):
                break
            # Check if app is still running
            if not self.app.is_running:
                return default

        return result_container["value"]

    def ask_multiline(self, question: str, default: str = "") -> Optional[str]:
        """
        Ask user for multiline text input (blocks until user responds).

        Args:
            question: Question to ask
            default: Default value

        Returns:
            User's multiline input text, or None if empty

        Example:
            body = ctx.textual.ask_multiline("Enter issue description:", default="")
        """
        # Event and result container for synchronization
        result_event = threading.Event()
        result_container = {"value": None}

        def _mount_textarea():
            # Handler when Ctrl+D is pressed
            def on_submitted(value: str):
                result_container["value"] = value

                # Show confirmation (truncated preview for multiline)
                preview = value.split('\n')[0][:50]
                if len(value.split('\n')) > 1 or len(value) > 50:
                    preview += "..."
                self.output_widget.append_output(f"  → {preview}")

                # Remove the textarea widget
                textarea_widget.remove()

                # Unblock the step
                result_event.set()

            # Create PromptTextArea widget that handles the submission
            textarea_widget = PromptTextArea(
                question=question,
                default=default,
                on_submit=on_submitted
            )

            # Mount the widget (it will auto-focus)
            self.output_widget.mount(textarea_widget)

        # Call from thread since executor runs in background thread
        try:
            self.app.call_from_thread(_mount_textarea)
        except Exception:
            # App is closing or worker was cancelled
            return default

        # BLOCK here until user responds (with timeout to allow cancellation)
        # Wait in loop with timeout so we can be interrupted
        while not result_event.is_set():
            if result_event.wait(timeout=0.5):
                break
            # Check if app is still running
            if not self.app.is_running:
                return default

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

    def ask_choice(self, question: str, choices: list[str]) -> Optional[str]:
        """
        Ask user to select from a list of choices (numbered menu).

        Args:
            question: Question to ask
            choices: List of string choices

        Returns:
            Selected choice string, or None if cancelled

        Example:
            version = ctx.textual.ask_choice(
                "Select version:",
                ["26.4.0", "26.3.0", "26.2.0"]
            )
        """
        if not choices:
            return None

        # Display choices as numbered list
        self.text(question, markup="bold cyan")
        self.text("")
        for i, choice in enumerate(choices, 1):
            self.text(f"  {i}. {choice}", markup="dim")
        self.text("")

        # Ask for selection
        while True:
            response = self.ask_text("Enter number", default="")

            if response is None or response.strip() == "":
                return None  # Cancelled

            try:
                index = int(response.strip()) - 1
                if 0 <= index < len(choices):
                    return choices[index]
                else:
                    self.text(f"Invalid selection. Please enter 1-{len(choices)}", markup="yellow")
            except ValueError:
                self.text("Invalid input. Please enter a number", markup="yellow")

    @contextmanager
    def loading(self, message: str = "Loading..."):
        """
        Show a loading indicator with a message (context manager).

        Args:
            message: Message to display while loading

        Example:
            with ctx.textual.loading("Generating commit message..."):
                response = ctx.ai.generate(messages)
        """
        # Create loading container with message and spinner
        loading_container = Container(
            Static(f"[dim]{message}[/dim]"),
            LoadingIndicator()
        )
        loading_container.styles.height = "auto"

        # Mount the loading widget
        self.mount(loading_container)

        try:
            yield
        finally:
            # Remove loading widget when done
            def _remove():
                try:
                    loading_container.remove()
                except Exception:
                    pass

            try:
                self.app.call_from_thread(_remove)
            except Exception:
                # App is closing or worker was cancelled
                pass

    def launch_external_cli(self, cli_name: str, prompt: str = None, cwd: str = None) -> int:
        """
        Launch an external CLI tool, suspending the TUI while it runs.

        Args:
            cli_name: Name of the CLI to launch (e.g., "claude", "gemini")
            prompt: Optional initial prompt to pass to the CLI
            cwd: Working directory (default: current)

        Returns:
            Exit code from the CLI tool

        Example:
            exit_code = ctx.textual.launch_external_cli("claude", prompt="Fix this bug")
        """
        from titan_cli.external_cli.launcher import CLILauncher
        from titan_cli.external_cli.configs import CLI_REGISTRY

        # Container for result (since we need to pass it from main thread back to worker)
        result_container = {"exit_code": None}
        result_event = threading.Event()

        def _launch():
            # Suspend TUI, launch CLI, restore TUI
            with self.app.suspend():
                # Get CLI configuration for proper flag usage
                config = CLI_REGISTRY.get(cli_name, {})
                launcher = CLILauncher(
                    cli_name,
                    install_instructions=config.get("install_instructions"),
                    prompt_flag=config.get("prompt_flag")
                )
                exit_code = launcher.launch(prompt=prompt, cwd=cwd)
                result_container["exit_code"] = exit_code

            # Signal completion
            result_event.set()

        # Run in main thread (because suspend() must run on main thread)
        try:
            self.app.call_from_thread(_launch)
        except Exception:
            # App is closing or worker was cancelled
            return -1

        # Wait for completion (with timeout to allow cancellation)
        while not result_event.is_set():
            if result_event.wait(timeout=0.5):
                break
            # Check if app is still running
            if not self.app.is_running:
                return -1

        return result_container["exit_code"]
