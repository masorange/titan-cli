"""Headless workflow run commands."""

import json
import sys
import threading
from typing import Optional

import typer

from titan_cli.application.models.requests import StartWorkflowRequest
from titan_cli.application.models.requests import SubmitPromptResponseRequest
from titan_cli.application.runtime.status import RunSessionStatus
from titan_cli.commands.headless.common import (
    fail_headless_command,
    parse_json_array,
    parse_json_object,
    run_headless_operation,
)
from titan_cli.ports.protocol import CommandType
from titan_cli.ports.protocol import EngineCommand
from titan_cli.runtime.container import TitanRuntimeContainer
from titan_cli.runtime.output import output_presenter, to_jsonable


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
        mode: str = typer.Option(
            "run_result",
            "--mode",
            help="Headless protocol output mode: run_result or event_stream.",
        ),
        output_json: bool = typer.Option(
            False,
            "--json",
            help="Print a machine-readable JSON response.",
        ),
    ):
        """Run a workflow through the headless V1 adapter binding."""
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

            if mode == "event_stream":
                _run_event_stream_mode(container, request)
                return

            if mode != "run_result":
                raise typer.BadParameter("--mode must be either 'run_result' or 'event_stream'")

            response = run_headless_operation(
                lambda: container.workflow_service().start_workflow(request)
            )
            if response.result is None:
                raise ValueError(
                    "run_result mode requires a terminal run. Use event_stream mode or pre-seed prompt responses."
                )
            output_presenter(output_json).write(response.result)
        except typer.BadParameter:
            raise
        except Exception as exc:
            fail_headless_command(exc, as_json=output_json)

    return app


def _run_event_stream_mode(container: TitanRuntimeContainer, request: StartWorkflowRequest) -> None:
    """Run a workflow and expose the official V1 event stream over stdio."""
    service = run_headless_operation(lambda: container.workflow_service())
    session = run_headless_operation(lambda: service.create_run(request))
    last_sequence = 0

    worker = threading.Thread(
        target=lambda: service.execute_run(session, request),
    )
    worker.start()

    try:
        while True:
            for event in run_headless_operation(
                lambda: list(
                    service.stream_events(
                        session.run_id,
                        replay=True,
                        timeout_seconds=0.1,
                    )
                )
            ):
                if event.sequence <= last_sequence:
                    continue
                typer.echo(json.dumps(to_jsonable(event)))
                last_sequence = event.sequence

            run_state = run_headless_operation(lambda: service.get_run(session.run_id))
            if run_state is None:
                return

            if run_state.status in {
                RunSessionStatus.COMPLETED,
                RunSessionStatus.FAILED,
                RunSessionStatus.CANCELLED,
            }:
                return

            if run_state.status == RunSessionStatus.WAITING_FOR_INPUT:
                command = _read_engine_command(run_state.run_id)
                if command.type == CommandType.SUBMIT_PROMPT_RESPONSE:
                    prompt_id = str(command.payload.get("prompt_id") or "")
                    run_headless_operation(
                        lambda: service.submit_prompt_response(
                            SubmitPromptResponseRequest(
                                run_id=command.run_id,
                                prompt_id=prompt_id,
                                value=command.payload.get("value"),
                            )
                        )
                    )
                    continue

                if command.type == CommandType.CANCEL_RUN:
                    reason = str(command.payload.get("reason") or "Run cancelled by user")
                    run_headless_operation(
                        lambda: service.cancel_run(command.run_id, reason=reason)
                    )
                    continue
    finally:
        worker.join(timeout=1.0)


def _read_engine_command(run_id: str) -> EngineCommand:
    """Read a single inbound V1 command from stdin as JSON."""
    line = sys.stdin.readline()
    if not line:
        raise ValueError("stdin closed while waiting for an inbound EngineCommand")

    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"stdin must contain valid JSON Lines commands: {exc.msg}") from exc

    if not isinstance(payload, dict):
        raise ValueError("stdin command must be a JSON object")

    command_run_id = str(payload.get("run_id") or run_id)
    command_type = payload.get("type")
    if command_type not in {CommandType.SUBMIT_PROMPT_RESPONSE, CommandType.CANCEL_RUN}:
        raise ValueError("stdin command type must be 'submit_prompt_response' or 'cancel_run'")

    return EngineCommand(
        type=CommandType(command_type),
        run_id=command_run_id,
        payload=dict(payload.get("payload") or {}),
    )
