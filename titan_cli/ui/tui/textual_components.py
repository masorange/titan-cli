"""
Textual UI Components container for workflow context.

Provides utilities for workflow steps to mount widgets and request user input in the TUI.

Steps can import widgets directly from titan_cli.ui.tui.widgets and mount them using ctx.textual.
"""

import threading
from typing import Optional
from contextlib import contextmanager
from textual.widget import Widget
from textual.widgets import LoadingIndicator, Static, Markdown
from textual.containers import Container
from titan_cli.ui.tui.widgets import Panel, PromptInput, PromptTextArea


class TextualComponents:
    """
    Textual UI utilities for workflow steps.

    All text styling uses the theme system for consistent colors across themes.

    Steps can use these utilities to:
    - Display panels with consistent styling
    - Append text with theme-based styling
    - Request user input interactively
    - Mount custom widgets to the output panel

    Example:
        def my_step(ctx):
            # Show a panel
            ctx.textual.panel("Warning message", panel_type="warning")

            # Append styled text (uses theme system)
            ctx.textual.dim_text("Fetching data...")
            ctx.textual.success_text("Operation completed!")
            ctx.textual.error_text("Failed to connect")
            ctx.textual.bold_primary_text("AI Analysis Results")

            # Append plain text
            ctx.textual.text("Processing...")

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
        self._active_step_container = None

    def begin_step(self, step_name: str) -> None:
        """
        Begin a new step by creating a StepContainer and auto-scrolling to it.

        Args:
            step_name: Name of the step
        """
        from titan_cli.ui.tui.widgets import StepContainer

        def _create_container():
            container = StepContainer(step_name=step_name)
            self.output_widget.mount(container)
            self._active_step_container = container
            # Auto-scroll to show the new step
            self.output_widget._scroll_to_end()

        try:
            self.app.call_from_thread(_create_container)
        except Exception:
            pass

    def end_step(self, result_type: str) -> None:
        """
        End the current step by updating its container color.

        Args:
            result_type: One of 'success', 'skip', 'error'
        """
        if not self._active_step_container:
            return

        def _update_container():
            if self._active_step_container:
                self._active_step_container.set_result(result_type)
                self._active_step_container = None

        try:
            self.app.call_from_thread(_update_container)
        except Exception:
            pass

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
            # Mount to active step container if it exists, otherwise to output widget
            target = self._active_step_container if self._active_step_container else self.output_widget
            target.mount(widget)

        # call_from_thread already blocks until the function completes
        try:
            self.app.call_from_thread(_mount)
        except Exception:
            # App is closing or worker was cancelled
            pass

    def text(self, text: str) -> None:
        """
        Append plain text without styling.

        For styled text, use specific methods: dim_text(), success_text(), etc.

        Args:
            text: Text to append

        Example:
            ctx.textual.text("Processing...")
            ctx.textual.text("")  # Empty line
        """
        def _append():
            # If there's an active step container, append to it; otherwise to output widget
            if self._active_step_container:
                from textual.widgets import Static
                widget = Static(text)
                widget.styles.height = "auto"
                self._active_step_container.mount(widget)
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
            # Mount to active step container if it exists, otherwise to output widget
            target = self._active_step_container if self._active_step_container else self.output_widget
            target.mount(md_widget)
            # Trigger autoscroll after mounting
            self.output_widget._scroll_to_end()

        # call_from_thread already blocks until the function completes
        try:
            self.app.call_from_thread(_mount)
        except Exception:
            # App is closing or worker was cancelled
            pass

    def panel(self, text: str, panel_type: str = "info") -> None:
        """
        Show a panel with consistent styling.

        Args:
            text: Text to display in the panel
            panel_type: Type of panel - "info", "success", "warning", or "error"

        Example:
            ctx.textual.panel("Operation completed successfully!", panel_type="success")
            ctx.textual.panel("Warning: This action cannot be undone", panel_type="warning")
        """
        panel_widget = Panel(text=text, panel_type=panel_type)
        self.mount(panel_widget)

    def dim_text(self, text: str) -> None:
        """
        Append dim/muted text (uses theme system).

        Args:
            text: Text to display

        Example:
            ctx.textual.dim_text("Fetching versions for project: ECAPP")
        """
        from titan_cli.ui.tui.widgets import DimText
        widget = DimText(text)
        widget.styles.height = "auto"
        self.mount(widget)

    def success_text(self, text: str) -> None:
        """
        Append success text (green, uses theme system).

        Args:
            text: Text to display

        Example:
            ctx.textual.success_text("Commit created: abc1234")
        """
        from titan_cli.ui.tui.widgets import SuccessText
        widget = SuccessText(text)
        widget.styles.height = "auto"
        self.mount(widget)

    def error_text(self, text: str) -> None:
        """
        Append error text (red, uses theme system).

        Args:
            text: Text to display

        Example:
            ctx.textual.error_text("Failed to connect to API")
        """
        from titan_cli.ui.tui.widgets import ErrorText
        widget = ErrorText(text)
        widget.styles.height = "auto"
        self.mount(widget)

    def warning_text(self, text: str) -> None:
        """
        Append warning text (yellow, uses theme system).

        Args:
            text: Text to display

        Example:
            ctx.textual.warning_text("This action will overwrite existing files")
        """
        from titan_cli.ui.tui.widgets import WarningText
        widget = WarningText(text)
        widget.styles.height = "auto"
        self.mount(widget)

    def primary_text(self, text: str) -> None:
        """
        Append primary colored text (uses theme system).

        Args:
            text: Text to display

        Example:
            ctx.textual.primary_text("Processing items...")
        """
        from titan_cli.ui.tui.widgets import PrimaryText
        widget = PrimaryText(text)
        widget.styles.height = "auto"
        self.mount(widget)

    def bold_text(self, text: str) -> None:
        """
        Append bold text.

        Args:
            text: Text to display

        Example:
            ctx.textual.bold_text("Important: Read carefully")
        """
        from titan_cli.ui.tui.widgets import BoldText
        widget = BoldText(text)
        widget.styles.height = "auto"
        self.mount(widget)

    def bold_primary_text(self, text: str) -> None:
        """
        Append bold text with primary theme color.

        Args:
            text: Text to display

        Example:
            ctx.textual.bold_primary_text("AI Analysis Results")
        """
        from titan_cli.ui.tui.widgets import BoldPrimaryText
        widget = BoldPrimaryText(text)
        widget.styles.height = "auto"
        self.mount(widget)

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
