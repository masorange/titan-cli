"""
Workflow Execution Screen

Screen for executing workflows and displaying progress in real-time.
"""
import os
from typing import Any, List, Optional, Dict

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static
from textual.containers import Container, VerticalScroll
from textual.worker import Worker, WorkerState

from titan_cli.ui.tui.widgets import HeaderWidget
from titan_cli.ui.tui.icons import Icons

from titan_cli.core.secrets import SecretManager
from titan_cli.core.workflows import ParsedWorkflow
from titan_cli.engine.builder import WorkflowContextBuilder
from titan_cli.core.workflows.workflow_exceptions import (
    WorkflowNotFoundError,
    WorkflowExecutionError,
)
from titan_cli.ui.tui.textual_workflow_executor import TextualWorkflowExecutor
from titan_cli.ui.tui.widgets.text import DimText
from .base import BaseScreen

from textual.containers import Horizontal

class WorkflowExecutionScreen(BaseScreen):
    """
    Screen for executing a workflow with real-time progress display.

    The internal structure (progress tracking, output handling, etc.)
    will be implemented separately.
    """

    BINDINGS = [
        ("escape", "cancel_execution", "Cancel"),
        ("q", "cancel_execution", "Cancel"),
    ]

    CSS = """
    WorkflowExecutionScreen {
        align: center middle;
    }

    #workflow-description {
        width: 100%;
        text-align: center;
        padding-bottom: 1;
    }

    #execution-container {
        width: 100%;
        height: 1fr;
        background: $surface-lighten-1;
        padding: 0 2 1 2;
    }

    #steps-panel {
        width: 20%;
        height: 100%;
        border: round $primary;
        border-title-align: center;
        background: $surface-lighten-1;
        padding: 0;
    }

    #steps-content {
        padding: 1;
    }

    #workflow-execution-panel {
        width: 80%;
        height: 100%;
        border: round $primary;
        border-title-align: center;
        background: $surface-lighten-1;
        padding: 0;
    }

    #execution-content {
        padding: 1;
    }
    """

    def __init__(self, config, workflow_name: str, **kwargs):
        super().__init__(
            config,
            title=f"{Icons.WORKFLOW} Executing: {workflow_name}",
            show_back=True,
            **kwargs
        )
        self.workflow_name = workflow_name
        self.workflow: Optional[ParsedWorkflow] = None
        self._worker: Optional[Worker] = None
        self._original_cwd = os.getcwd()
        self._should_auto_back = False  # Flag to trigger auto-back when worker finishes

    def compose_content(self) -> ComposeResult:
        """Compose the workflow execution screen."""
        with Container(id="execution-container"):
            yield DimText(id="workflow-description")
            with Horizontal():
                    left_panel = VerticalScroll(id="steps-panel")
                    left_panel.border_title = "Steps"
                    with left_panel:
                        yield StepsContent(id="steps-content")

                    right_panel = VerticalScroll(id="workflow-execution-panel")
                    right_panel.border_title = "Workflow Execution"
                    with right_panel:
                        yield WorkflowExecutionContent(id="execution-content")            
                
    def on_mount(self) -> None:
        """Start workflow execution when screen is mounted."""
        self._load_and_execute_workflow()

    def _load_and_execute_workflow(self) -> None:
        """Load and execute the workflow."""
        try:
            # Load workflow
            self.workflow = self.config.workflows.get_workflow(self.workflow_name)
            # if not self.workflow:
                # TODO Create empty error screen 
                # self._update_workflow_info(
                #     f"[red]Error: Workflow '{self.workflow_name}' not found[/red]"
                # )
                # return

            self._update_header_title(f"{Icons.WORKFLOW} {self.workflow.name}")
            self._update_description(self.workflow.description or "")

            # Create step widgets for non-hook steps
            steps_widget = self.query_one("#steps-content", StepsContent)
            steps_widget.set_steps(self.workflow.steps)

            self._output("Preparing to execute workflow...")

            # Execute workflow in background thread (not async worker)
            self._worker = self.run_worker(
                self._execute_workflow,
                name="workflow_executor",
                thread=True
            )

        except (WorkflowNotFoundError, WorkflowExecutionError):
            pass
            # TODO Create empty error screen
            # self._update_workflow_info(f"[red]Error: {e}[/red]")
        except Exception:
            pass
            # TODO Create empty error screen
            # self._update_workflow_info(
            #     f"[red]Unexpected error: {type(e).__name__} - {e}[/red]"
            # )

    def _execute_workflow(self) -> None:
        """Execute the workflow in a background thread."""
        try:
            # Change to project directory if specified
            if self.config.active_project_path:
                os.chdir(self.config.active_project_path)

            # Create secret manager
            secrets = SecretManager(
                project_path=self.config.active_project_path or self.config.project_root
            )

            # Build workflow context (without UI - executor handles messaging)
            ctx_builder = WorkflowContextBuilder(
                plugin_registry=self.config.registry,
                secrets=secrets,
                ai_config=self.config.config.ai,
            )

            # Add AI if configured
            ctx_builder.with_ai()

            # Add registered plugins to context
            for plugin_name in self.config.registry.list_installed():
                plugin = self.config.registry.get_plugin(plugin_name)
                if plugin and hasattr(ctx_builder, f"with_{plugin_name}"):
                    try:
                        client = plugin.get_client()
                        getattr(ctx_builder, f"with_{plugin_name}")(client)
                    except Exception:
                        # Plugin client initialization failed - workflow steps
                        # using this plugin will fail gracefully
                        pass

            # Build context and create executor
            execution_context = ctx_builder.build()
            executor = TextualWorkflowExecutor(
                plugin_registry=self.config.registry,
                workflow_registry=self.config.workflows,
                message_target=self  # Pass self to receive messages
            )

            # Execute workflow (this is synchronous and may take time)
            executor.execute(self.workflow, execution_context)

        except (WorkflowNotFoundError, WorkflowExecutionError) as e:
            self._output(f"\n[red]{Icons.ERROR} Workflow failed: {e}[/red]")
            self._output("[dim]Press ESC or Q to return[/dim]")
        except Exception as e:
            self._output(f"\n[red]{Icons.ERROR} Unexpected error: {type(e).__name__}: {e}[/red]")
            self._output("[dim]Press ESC or Q to return[/dim]")
        finally:
            # Restore original working directory
            os.chdir(self._original_cwd)

    def _update_header_title(self, title: str) -> None:
        """Update the header title."""
        try:
            header = self.query_one(HeaderWidget)
            header.title = title
        except Exception:
            pass

    def _update_description(self, description: str) -> None:
        """Update the workflow description."""
        try:
            header = self.query_one("#workflow-description", DimText)
            header.update(description)
        except Exception:
            pass

    def _output(self, text: str) -> None:
        """Helper to append output to execution widget."""
        try:
            execution_widget = self.query_one("#execution-content", WorkflowExecutionContent)
            execution_widget.append_output(text)
        except Exception:
            pass

    # Generic message handler for TextualWorkflowExecutor events
    def on_textual_workflow_executor_workflow_started(
        self, message: TextualWorkflowExecutor.WorkflowStarted
    ) -> None:
        """Handle workflow started event."""
        self._handle_workflow_event(message)

    def on_textual_workflow_executor_step_started(
        self, message: TextualWorkflowExecutor.StepStarted
    ) -> None:
        """Handle step started event."""
        self._handle_workflow_event(message)

    def on_textual_workflow_executor_step_completed(
        self, message: TextualWorkflowExecutor.StepCompleted
    ) -> None:
        """Handle step completed event."""
        self._handle_workflow_event(message)

    def on_textual_workflow_executor_step_failed(
        self, message: TextualWorkflowExecutor.StepFailed
    ) -> None:
        """Handle step failed event."""
        self._handle_workflow_event(message)

    def on_textual_workflow_executor_step_skipped(
        self, message: TextualWorkflowExecutor.StepSkipped
    ) -> None:
        """Handle step skipped event."""
        self._handle_workflow_event(message)

    def on_textual_workflow_executor_workflow_completed(
        self, message: TextualWorkflowExecutor.WorkflowCompleted
    ) -> None:
        """Handle workflow completed event."""
        self._handle_workflow_event(message)

    def on_textual_workflow_executor_workflow_failed(
        self, message: TextualWorkflowExecutor.WorkflowFailed
    ) -> None:
        """Handle workflow failed event."""
        self._handle_workflow_event(message)

    def _handle_workflow_event(self, message) -> None:
        """Generic handler that delegates to widgets."""
        try:
            # Update steps widget if step-related
            if hasattr(message, 'step_id'):
                steps_widget = self.query_one("#steps-content", StepsContent)
                steps_widget.handle_event(message)

            # Update execution widget for output
            execution_widget = self.query_one("#execution-content", WorkflowExecutionContent)
            execution_widget.handle_event(message)
        except Exception:
            pass

    def _schedule_auto_back(self) -> None:
        """Schedule auto-back - will execute when worker finishes."""
        import time
        with open("/tmp/titan_debug.log", "a") as f:
            f.write(f"[{time.time():.3f}] SCREEN: Auto-back scheduled, setting flag\n")
        self._should_auto_back = True
        # Check if worker already finished
        self._check_and_pop_if_ready()

    def _check_and_pop_if_ready(self) -> None:
        """Check if we should pop screen (worker finished + auto-back scheduled)."""
        import time
        if self._should_auto_back and (not self._worker or self._worker.state != WorkerState.RUNNING):
            with open("/tmp/titan_debug.log", "a") as f:
                f.write(f"[{time.time():.3f}] SCREEN: Worker finished and auto-back ready, popping screen\n")
            self.app.pop_screen()

    def on_worker_state_changed(self, event) -> None:
        """Handle worker state changes."""
        import time
        with open("/tmp/titan_debug.log", "a") as f:
            f.write(f"[{time.time():.3f}] SCREEN: Worker state changed to {event.state}\n")
        # When worker finishes, check if we should auto-back
        if event.state != WorkerState.RUNNING:
            self._check_and_pop_if_ready()

    def action_cancel_execution(self) -> None:
        """Cancel workflow execution and go back."""
        # Cancel worker if running
        if self._worker and self._worker.state == WorkerState.RUNNING:
            # Try to cancel, but don't wait for it to finish
            # The worker thread may be blocked, so we just move on
            try:
                self._worker.cancel()
            except Exception:
                pass

        # Restore working directory
        try:
            os.chdir(self._original_cwd)
        except Exception:
            pass

        # Pop screen immediately without waiting for worker
        self.app.pop_screen()

class StepsContent(Widget):
    """Widget to display workflow steps and their statuses."""

    DEFAULT_CSS = """
    StepsContent {
        width: 100%;
        height: auto;
        layout: vertical;
    }

    .step-widget {
        width: 100%;
        height: auto;
        padding: 0 1 1 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.steps: List[Dict[str, Any]] = []
        self._step_widgets: Dict[str, Static] = {}

    def set_steps(self, steps: List[Dict[str, Any]]) -> None:
        """Set the steps to display."""
        self.steps = steps

        for idx, step_data in enumerate(steps):
            if step_data.get("hook"):
                continue

            step_id = step_data.get("id") or f"step_{idx}"
            step_name = step_data.get("name") or step_id

            step_widget = Static(f"{Icons.PENDING} {step_name}", classes="step-widget")
            self._step_widgets[step_id] = step_widget
            self.mount(step_widget)

    def update_step(self, step_id: str, text: str) -> None:
        """Update a specific step's display."""
        if step_id in self._step_widgets:
            self._step_widgets[step_id].update(text)

    def set_step_running(self, step_id: str, step_name: str) -> None:
        """Mark a step as running."""
        self.update_step(step_id, f"{Icons.RUNNING} [cyan]{step_name}[/cyan]")

    def set_step_success(self, step_id: str, step_name: str) -> None:
        """Mark a step as successful."""
        self.update_step(step_id, f"{Icons.SUCCESS} [green]{step_name}[/green]")

    def set_step_failed(self, step_id: str, step_name: str) -> None:
        """Mark a step as failed."""
        self.update_step(step_id, f"{Icons.ERROR} [red]{step_name}[/red]")

    def set_step_skipped(self, step_id: str, step_name: str) -> None:
        """Mark a step as skipped."""
        self.update_step(step_id, f"{Icons.SKIPPED} [yellow]{step_name}[/yellow]")

    def handle_event(self, message) -> None:
        """Handle workflow events generically."""
        from titan_cli.ui.tui.textual_workflow_executor import TextualWorkflowExecutor

        if isinstance(message, TextualWorkflowExecutor.StepStarted):
            self.update_step(message.step_id, f"{Icons.RUNNING} [cyan]{message.step_name}[/cyan]")
        elif isinstance(message, TextualWorkflowExecutor.StepCompleted):
            self.update_step(message.step_id, f"{Icons.SUCCESS} [green]{message.step_name}[/green]")
        elif isinstance(message, TextualWorkflowExecutor.StepFailed):
            self.update_step(message.step_id, f"{Icons.ERROR} [red]{message.step_name}[/red]")
        elif isinstance(message, TextualWorkflowExecutor.StepSkipped):
            self.update_step(message.step_id, f"{Icons.SKIPPED} [yellow]{message.step_name}[/yellow]")


class WorkflowExecutionContent(Widget):
    """Widget to display workflow execution output."""

    # Allow children to receive focus (for input widgets)
    can_focus_children = True

    DEFAULT_CSS = """
    WorkflowExecutionContent {
        width: 100%;
        height: auto;
        layout: vertical;
    }

    WorkflowExecutionContent > Static {
        width: 100%;
        height: auto;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose the execution content."""
        # Don't yield anything - content will be mounted dynamically
        return
        yield  # Make this a generator

    def append_output(self, text: str) -> None:
        """Append text to the output."""
        # Mount each line as a separate Static widget to preserve order
        try:
            text_widget = Static(text)
            self.mount(text_widget)
            # Auto-scroll to show new content
            self._scroll_to_end()
        except Exception:
            pass

    def _scroll_to_end(self) -> None:
        """Scroll the parent container to show the end."""
        try:
            # Get the parent VerticalScroll container
            parent = self.parent
            if parent and hasattr(parent, 'scroll_end'):
                parent.scroll_end(animate=False)
        except Exception:
            pass

    def on_descendant_mount(self, event) -> None:
        """Auto-scroll when any widget is mounted as a descendant."""
        # Don't auto-scroll if we're mounting a PromptInput (it will handle its own scroll)
        from titan_cli.ui.tui.textual_components import PromptInput

        # Skip scroll only if the widget itself is a PromptInput
        # (not if it's a child of PromptInput, to avoid blocking scroll after PromptInput is removed)
        if not isinstance(event.widget, PromptInput):
            self._scroll_to_end()

    def handle_event(self, message) -> None:
        """Handle workflow events generically."""
        from titan_cli.ui.tui.textual_workflow_executor import TextualWorkflowExecutor
        from titan_cli.ui.tui.widgets import Panel

        if isinstance(message, TextualWorkflowExecutor.WorkflowStarted):
            self.append_output(f"\n[bold cyan]🚀 Starting workflow: {message.workflow_name}[/bold cyan]")

        elif isinstance(message, TextualWorkflowExecutor.StepStarted):
            self.append_output(f"[cyan]→ Step {message.step_index}: {message.step_name}[/cyan]")

        elif isinstance(message, TextualWorkflowExecutor.StepCompleted):
            self.append_output(f"[green]{Icons.SUCCESS} Completed: {message.step_name}[/green]\n")

        elif isinstance(message, TextualWorkflowExecutor.StepFailed):
            # Mount error panel
            try:
                self.mount(Panel(f"Failed: {message.step_name} - {message.error_message}", panel_type="error"))
                self._scroll_to_end()
            except Exception:
                pass

            if message.on_error == "continue":
                self.append_output(f"[yellow]   {Icons.WARNING}  Continuing despite error[/yellow]\n")
            else:
                self.append_output("")

        elif isinstance(message, TextualWorkflowExecutor.StepSkipped):
            # Mount warning panel for skipped steps
            try:
                self.mount(Panel(f"Skipped: {message.step_name}", panel_type="warning"))
                self._scroll_to_end()
            except Exception:
                pass

        elif isinstance(message, TextualWorkflowExecutor.WorkflowCompleted):
            # DEBUG: Log receipt
            import time
            with open("/tmp/titan_debug.log", "a") as f:
                f.write(f"[{time.time():.3f}] SCREEN: Received WorkflowCompleted, is_nested={message.is_nested}\n")

            # Show success toast instead of inline message
            try:
                with open("/tmp/titan_debug.log", "a") as f:
                    f.write(f"[{time.time():.3f}] SCREEN: About to call notify\n")
                self.app.notify(f"✨ Workflow completed: {message.workflow_name}", severity="information", timeout=5)
                with open("/tmp/titan_debug.log", "a") as f:
                    f.write(f"[{time.time():.3f}] SCREEN: notify called successfully\n")
            except Exception as e:
                with open("/tmp/titan_debug.log", "a") as f:
                    f.write(f"[{time.time():.3f}] SCREEN: notify failed: {e}\n")
                # Fallback if notify fails
                self.append_output(f"\n[bold green]✨ Workflow completed: {message.workflow_name}[/bold green]")

            # Schedule auto-back after a short delay (only if not nested)
            if not message.is_nested:
                with open("/tmp/titan_debug.log", "a") as f:
                    f.write(f"[{time.time():.3f}] SCREEN: Setting timer for auto-back flag\n")
                # Don't pop immediately - wait for worker to finish, then pop
                self.set_timer(3.0, self._schedule_auto_back)
            else:
                with open("/tmp/titan_debug.log", "a") as f:
                    f.write(f"[{time.time():.3f}] SCREEN: Workflow is nested, skipping auto-back\n")

        elif isinstance(message, TextualWorkflowExecutor.WorkflowFailed):
            # Show error toast for workflow failure
            self.app.notify(f"❌ Workflow failed at step: {message.step_name}", severity="error", timeout=10)
            self.append_output(f"[red]{message.error_message}[/red]")

