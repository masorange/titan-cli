"""Headless workflow discovery commands."""

from typing import Optional

import typer

from titan_cli.commands.headless.common import (
    fail_headless_command,
    run_headless_operation,
)
from titan_cli.runtime.container import TitanRuntimeContainer
from titan_cli.runtime.output import output_presenter


def build_app(container: TitanRuntimeContainer) -> typer.Typer:
    """Build workflow headless commands."""
    app = typer.Typer(name="workflows", help="Discover and describe workflows.")

    @app.command("list")
    def list_workflows(
        project_path: Optional[str] = typer.Option(
            None,
            "--project-path",
            help="Project directory used to resolve project workflows and plugin config.",
        ),
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """List workflows without launching the TUI or HTTP backend."""
        try:
            workflows = run_headless_operation(
                lambda: container.workflow_service().list_workflows(
                    project_path=project_path
                )
            )
            output_presenter(output_json).write({"items": workflows})
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    @app.command("describe")
    def describe_workflow(
        workflow_name: str = typer.Argument(..., help="Workflow name to describe."),
        project_path: Optional[str] = typer.Option(
            None,
            "--project-path",
            help="Project directory used to resolve project workflows and plugin config.",
        ),
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """Describe a resolved workflow, including inherited and hook steps."""
        try:
            workflow = run_headless_operation(
                lambda: container.workflow_service().describe_workflow(
                    workflow_name=workflow_name,
                    project_path=project_path,
                )
            )
            if workflow is None:
                raise typer.BadParameter(f"Workflow '{workflow_name}' not found")
            output_presenter(output_json).write(workflow)
        except typer.BadParameter:
            raise
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    return app

