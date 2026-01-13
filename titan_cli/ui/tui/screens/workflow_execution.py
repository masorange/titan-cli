"""
Workflow Execution Screen

Screen for executing workflows and displaying progress in real-time.
"""
import os
from typing import Optional, Dict

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Container, Vertical
from textual.worker import Worker, WorkerState

from titan_cli.core.secrets import SecretManager
from titan_cli.core.workflows import ParsedWorkflow
from titan_cli.engine.builder import WorkflowContextBuilder
from titan_cli.core.workflows.workflow_exceptions import (
    WorkflowNotFoundError,
    WorkflowExecutionError,
)
from titan_cli.ui.tui.textual_workflow_executor import TextualWorkflowExecutor
from .base import BaseScreen


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

    #execution-container {
        width: 100%;
        height: 1fr;
        background: $surface-lighten-1;
        padding: 2;
    }

    #workflow-info {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    #steps-container {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    .step-widget {
        width: 100%;
        height: auto;
        padding: 0 1;
    }

    #output-container {
        width: 100%;
        height: 1fr;
        border: round $primary;
        padding: 1;
    }

    #output-text {
        width: 100%;
        height: auto;
    }
    """

    def __init__(self, config, workflow_name: str, **kwargs):
        super().__init__(
            config,
            title=f"⚡ Executing: {workflow_name}",
            show_back=False,
            **kwargs
        )
        self.workflow_name = workflow_name
        self.workflow: Optional[ParsedWorkflow] = None
        self._worker: Optional[Worker] = None
        self._original_cwd = os.getcwd()
        self._step_widgets: Dict[str, Static] = {}  # Map step_id to widget
        self._output_lines = []

    def compose_content(self) -> ComposeResult:
        """Compose the workflow execution screen."""
        with Container(id="execution-container"):
            # Workflow info section
            yield Static(
                f"Loading workflow: {self.workflow_name}...",
                id="workflow-info"
            )

            # Steps section
            with Vertical(id="steps-container"):
                pass  # Steps will be added dynamically

            # Output section
            with Container(id="output-container"):
                yield Static("", id="output-text")

    def on_mount(self) -> None:
        """Start workflow execution when screen is mounted."""
        self._load_and_execute_workflow()

    def _load_and_execute_workflow(self) -> None:
        """Load and execute the workflow."""
        try:
            # Load workflow
            self.workflow = self.config.workflows.get_workflow(self.workflow_name)
            if not self.workflow:
                self._update_workflow_info(
                    f"[red]Error: Workflow '{self.workflow_name}' not found[/red]"
                )
                return

            # Update workflow info
            info_text = f"[bold cyan]{self.workflow.name}[/bold cyan]\n"
            if self.workflow.description:
                info_text += f"[dim]{self.workflow.description}[/dim]\n"
            if self.workflow.source:
                info_text += f"[dim]Source: {self.workflow.source}[/dim]"
            self._update_workflow_info(info_text)

            # Create step widgets for non-hook steps
            steps_container = self.query_one("#steps-container", Vertical)
            for idx, step_data in enumerate(self.workflow.steps):
                if step_data.get("hook"):
                    continue

                step_id = step_data.get("id") or f"step_{idx}"
                step_name = step_data.get("name") or step_id

                step_widget = Static(
                    f"⏸️ {step_name}",
                    classes="step-widget"
                )
                self._step_widgets[step_id] = step_widget
                steps_container.mount(step_widget)

            self._append_output("Preparing to execute workflow...")

            # Execute workflow in background worker
            self._worker = self.run_worker(
                self._execute_workflow_async(),
                name="workflow_executor"
            )

        except (WorkflowNotFoundError, WorkflowExecutionError) as e:
            self._update_workflow_info(f"[red]Error: {e}[/red]")
        except Exception as e:
            self._update_workflow_info(
                f"[red]Unexpected error: {type(e).__name__} - {e}[/red]"
            )

    async def _execute_workflow_async(self) -> None:
        """Execute the workflow asynchronously."""
        try:
            # Change to project directory if specified
            if self.config.active_project_path:
                os.chdir(self.config.active_project_path)
                self._append_output(f"Working directory: {self.config.active_project_path}")

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

            self._append_output("Starting workflow execution...")

            # Execute workflow (this is synchronous and may take time)
            executor.execute(self.workflow, execution_context)

            # Execution completed - messages were sent during execution
            self._append_output("\n[dim]Press ESC or Q to return[/dim]")

        except (WorkflowNotFoundError, WorkflowExecutionError) as e:
            self._append_output(f"\n[red]❌ Workflow failed: {e}[/red]")
            self._append_output("[dim]Press ESC or Q to return[/dim]")
        except Exception as e:
            self._append_output(f"\n[red]❌ Unexpected error: {type(e).__name__}: {e}[/red]")
            self._append_output("[dim]Press ESC or Q to return[/dim]")
        finally:
            # Restore original working directory
            os.chdir(self._original_cwd)

    def _update_workflow_info(self, text: str) -> None:
        """Update the workflow info widget."""
        try:
            info_widget = self.query_one("#workflow-info", Static)
            info_widget.update(text)
        except Exception:
            pass

    def _update_step_widget(self, step_id: str, text: str) -> None:
        """Update a step widget's display."""
        if step_id in self._step_widgets:
            self._step_widgets[step_id].update(text)

    def _append_output(self, text: str) -> None:
        """Append text to the output panel."""
        self._output_lines.append(text)
        try:
            output_widget = self.query_one("#output-text", Static)
            output_widget.update("\n".join(self._output_lines))
        except Exception:
            pass

    # Message handlers for TextualWorkflowExecutor events
    def on_textual_workflow_executor_workflow_started(
        self, message: TextualWorkflowExecutor.WorkflowStarted
    ) -> None:
        """Handle workflow started event."""
        self._append_output(f"\n[bold cyan]🚀 Starting workflow: {message.workflow_name}[/bold cyan]")
        if message.description:
            self._append_output(f"[dim]{message.description}[/dim]")
        self._append_output(f"[dim]Total steps: {message.total_steps}[/dim]\n")

    def on_textual_workflow_executor_step_started(
        self, message: TextualWorkflowExecutor.StepStarted
    ) -> None:
        """Handle step started event."""
        self._update_step_widget(message.step_id, f"⏳ [cyan]{message.step_name}[/cyan]")
        self._append_output(f"[cyan]→ Step {message.step_index}: {message.step_name}[/cyan]")

    def on_textual_workflow_executor_step_completed(
        self, message: TextualWorkflowExecutor.StepCompleted
    ) -> None:
        """Handle step completed event."""
        self._update_step_widget(message.step_id, f"✅ [green]{message.step_name}[/green]")
        self._append_output(f"[green]✅ Completed: {message.step_name}[/green]\n")

    def on_textual_workflow_executor_step_failed(
        self, message: TextualWorkflowExecutor.StepFailed
    ) -> None:
        """Handle step failed event."""
        self._update_step_widget(message.step_id, f"❌ [red]{message.step_name}[/red]")
        self._append_output(f"[red]❌ Failed: {message.step_name}[/red]")
        self._append_output(f"[red]   Error: {message.error_message}[/red]")
        if message.on_error == "continue":
            self._append_output("[yellow]   ⚠️  Continuing despite error[/yellow]\n")
        else:
            self._append_output("")

    def on_textual_workflow_executor_step_skipped(
        self, message: TextualWorkflowExecutor.StepSkipped
    ) -> None:
        """Handle step skipped event."""
        self._update_step_widget(message.step_id, f"⏭️ [yellow]{message.step_name}[/yellow]")
        self._append_output(f"[yellow]⏭️ Skipped: {message.step_name}[/yellow]\n")

    def on_textual_workflow_executor_workflow_completed(
        self, message: TextualWorkflowExecutor.WorkflowCompleted
    ) -> None:
        """Handle workflow completed event."""
        self._append_output(f"\n[bold green]✅ Workflow completed: {message.workflow_name}[/bold green]")

    def on_textual_workflow_executor_workflow_failed(
        self, message: TextualWorkflowExecutor.WorkflowFailed
    ) -> None:
        """Handle workflow failed event."""
        self._append_output(f"\n[bold red]❌ Workflow failed at step: {message.step_name}[/bold red]")
        self._append_output(f"[red]{message.error_message}[/red]")

    def action_cancel_execution(self) -> None:
        """Cancel workflow execution and go back."""
        # Cancel worker if running
        if self._worker and self._worker.state == WorkerState.RUNNING:
            self._worker.cancel()

        # Restore working directory
        os.chdir(self._original_cwd)

        self.app.pop_screen()
