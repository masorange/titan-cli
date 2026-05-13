"""Headless workflow run commands."""

import json
import sys
import threading
from typing import Any, Optional

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
from titan_cli.core.logging import get_logger
from titan_cli.ports.protocol import CommandType
from titan_cli.ports.protocol import EngineCommand
from titan_cli.ports.protocol import EngineEvent
from titan_cli.runtime.container import TitanRuntimeContainer
from titan_cli.runtime.output import output_presenter, to_jsonable


def _protocol_logger():
    """Return the structured logger for headless V1 communications."""
    return get_logger("titan.headless.protocol")


def _event_log_fields(event: EngineEvent) -> dict[str, Any]:
    """Return safe structured log fields for an outbound protocol event."""
    fields: dict[str, Any] = {
        "run_id": event.run_id,
        "sequence": event.sequence,
        "event_type": str(event.type),
    }
    payload = event.payload or {}
    step = payload.get("step")
    if step is not None:
        fields["step_id"] = getattr(step, "step_id", None)
    output = payload.get("output")
    if output is not None:
        fields["output_format"] = getattr(output, "format", None)
        fields["output_title_present"] = bool(getattr(output, "title", None))
        fields["output_content_length"] = len(getattr(output, "content", "") or "")
    prompt = payload.get("prompt")
    if prompt is not None:
        fields["prompt_id"] = getattr(prompt, "prompt_id", None)
        fields["prompt_type"] = getattr(prompt, "prompt_type", None)
        fields["prompt_message_length"] = len(getattr(prompt, "message", "") or "")
    return fields


def _command_log_fields(command: EngineCommand) -> dict[str, Any]:
    """Return safe structured log fields for an inbound protocol command."""
    payload = command.payload or {}
    value = payload.get("value")
    reason = payload.get("reason")
    fields: dict[str, Any] = {
        "run_id": command.run_id,
        "command_type": str(command.type),
        "prompt_id": payload.get("prompt_id"),
        "value_present": "value" in payload,
        "value_type": type(value).__name__ if value is not None else None,
        "value_length": len(value) if isinstance(value, str) else None,
        "reason_present": reason is not None,
        "reason_length": len(reason) if isinstance(reason, str) else None,
    }
    return fields


def _log_outbound_event(event: EngineEvent) -> None:
    """Log an outbound event without leaking protocol payload contents."""
    _protocol_logger().info("headless_protocol_event_emitted", **_event_log_fields(event))


def _log_inbound_command(command: EngineCommand) -> None:
    """Log an inbound command without logging sensitive values."""
    _protocol_logger().info("headless_protocol_command_received", **_command_log_fields(command))


def _log_protocol_state(event_name: str, **fields: Any) -> None:
    """Log non-payload communication lifecycle information."""
    _protocol_logger().info(event_name, **fields)


def _log_protocol_error(event_name: str, **fields: Any) -> None:
    """Log protocol and transport errors through Titan's logger."""
    _protocol_logger().error(event_name, **fields)


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
            _log_protocol_state(
                "headless_run_requested",
                workflow_name=workflow_name,
                mode=mode,
                project_path=project_path,
                preseeded_prompt_responses=len(request.prompt_responses),
            )

            if mode == "event_stream":
                _run_event_stream_mode(container, request)
                return

            if mode != "run_result":
                raise typer.BadParameter("--mode must be either 'run_result' or 'event_stream'")

            response = run_headless_operation(
                lambda: container.workflow_service().start_workflow(request)
            )
            _log_protocol_state(
                "headless_run_result_completed",
                run_id=response.run_id,
                session_status=str(response.status),
                terminal_status=(str(response.result.status) if response.result else None),
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
    _log_protocol_state(
        "headless_event_stream_started",
        run_id=session.run_id,
        workflow_name=request.workflow_name,
    )

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
                _log_outbound_event(event)
                typer.echo(json.dumps(to_jsonable(event)))
                last_sequence = event.sequence

            run_state = run_headless_operation(lambda: service.get_run(session.run_id))
            if run_state is None:
                _log_protocol_error(
                    "headless_event_stream_missing_run_state",
                    run_id=session.run_id,
                )
                return

            if run_state.status in {
                RunSessionStatus.COMPLETED,
                RunSessionStatus.FAILED,
                RunSessionStatus.CANCELLED,
            }:
                _log_protocol_state(
                    "headless_event_stream_finished",
                    run_id=session.run_id,
                    session_status=str(run_state.status),
                )
                return

            if run_state.status == RunSessionStatus.WAITING_FOR_INPUT:
                _log_protocol_state(
                    "headless_event_stream_waiting_for_input",
                    run_id=run_state.run_id,
                    prompt_id=(run_state.pending_prompt.prompt_id if run_state.pending_prompt else None),
                    prompt_type=(run_state.pending_prompt.prompt_type if run_state.pending_prompt else None),
                )
                command = _read_engine_command(run_state.run_id)
                _log_inbound_command(command)
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
        _log_protocol_state(
            "headless_event_stream_worker_joined",
            run_id=session.run_id,
            worker_alive=worker.is_alive(),
        )


def _read_engine_command(run_id: str) -> EngineCommand:
    """Read a single inbound V1 command from stdin as JSON."""
    line = sys.stdin.readline()
    if not line:
        _log_protocol_error(
            "headless_protocol_stdin_closed",
            run_id=run_id,
        )
        raise ValueError("stdin closed while waiting for an inbound EngineCommand")

    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        _log_protocol_error(
            "headless_protocol_command_parse_failed",
            run_id=run_id,
            error=str(exc),
            raw_length=len(line),
        )
        raise ValueError(f"stdin must contain valid JSON Lines commands: {exc.msg}") from exc

    if not isinstance(payload, dict):
        _log_protocol_error(
            "headless_protocol_command_invalid_shape",
            run_id=run_id,
            payload_type=type(payload).__name__,
        )
        raise ValueError("stdin command must be a JSON object")

    command_run_id = str(payload.get("run_id") or run_id)
    command_type = payload.get("type")
    if command_type not in {CommandType.SUBMIT_PROMPT_RESPONSE, CommandType.CANCEL_RUN}:
        _log_protocol_error(
            "headless_protocol_command_invalid_type",
            run_id=command_run_id,
            command_type=command_type,
        )
        raise ValueError("stdin command type must be 'submit_prompt_response' or 'cancel_run'")

    return EngineCommand(
        type=CommandType(command_type),
        run_id=command_run_id,
        payload=dict(payload.get("payload") or {}),
    )
