"""Headless workflow run commands."""

from typing import Optional

import typer

from titan_cli.application.models.requests import StartWorkflowRequest
from titan_cli.commands.headless.common import (
    fail_headless_command,
    parse_json_array,
    parse_json_object,
    run_headless_operation,
)
from titan_cli.runtime.container import TitanRuntimeContainer
from titan_cli.runtime.output import output_presenter


def build_app(container: TitanRuntimeContainer) -> typer.Typer:
    """Build headless workflow run commands."""
    app = typer.Typer(name="runs", help="Start and inspect workflow runs.")

    @app.command("start")
    def start_run(
        workflow_name: str = typer.Argument(..., help="Workflow name to run."),
        project_path: Optional[str] = typer.Option(
            None,
            "--project-path",
            help="Project directory used to resolve project workflows and plugin config.",
        ),
        params_json: Optional[str] = typer.Option(
            None,
            "--params-json",
            help="JSON object merged into the workflow context.",
        ),
        prompt_responses_json: Optional[str] = typer.Option(
            None,
            "--prompt-responses-json",
            help="JSON array of pre-seeded prompt responses for headless execution.",
        ),
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """Run a workflow synchronously without launching the TUI or HTTP backend."""
        try:
            request = StartWorkflowRequest(
                workflow_name=workflow_name,
                params=parse_json_object(params_json, "--params-json"),
                prompt_responses=parse_json_array(
                    prompt_responses_json,
                    "--prompt-responses-json",
                ),
                project_path=project_path,
                interaction_mode="headless",
            )
            response = run_headless_operation(
                lambda: container.workflow_service().start_workflow(request)
            )
            output_presenter(output_json).write(response)
        except typer.BadParameter:
            raise
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    return app

