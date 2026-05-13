from datetime import datetime, timezone

from titan_cli.ports.protocol import EngineCommand
from titan_cli.ports.protocol import EngineEvent
from titan_cli.ports.protocol import OutputPayload
from titan_cli.ports.protocol import PromptOption
from titan_cli.ports.protocol import PromptRequest
from titan_cli.ports.protocol import RunResult
from titan_cli.ports.protocol import RunStepResult
from titan_cli.ports.protocol import StepRef
from titan_cli.runtime.output import to_jsonable


def test_engine_event_serializes_to_v1_envelope_shape():
    event = EngineEvent(
        type="output_emitted",
        run_id="run-123",
        sequence=3,
        timestamp=datetime(2026, 5, 12, 10, 0, 2, tzinfo=timezone.utc),
        payload={
            "step": StepRef(
                step_id="check_status",
                step_name="Check Status",
                step_index=1,
            ),
            "output": OutputPayload(
                format="markdown",
                title="Repository Status",
                content="## Clean working tree",
            ),
        },
    )

    assert to_jsonable(event) == {
        "type": "output_emitted",
        "run_id": "run-123",
        "sequence": 3,
        "timestamp": "2026-05-12T10:00:02+00:00",
        "payload": {
            "step": {
                "step_id": "check_status",
                "step_name": "Check Status",
                "step_index": 1,
            },
            "output": {
                "format": "markdown",
                "title": "Repository Status",
                "content": "## Clean working tree",
                "metadata": {},
            },
        },
    }


def test_engine_command_serializes_to_v1_command_envelope_shape():
    command = EngineCommand(
        type="submit_prompt_response",
        run_id="run-123",
        timestamp=datetime(2026, 5, 12, 10, 0, 5, tzinfo=timezone.utc),
        payload={
            "prompt_id": "prompt-1",
            "value": True,
        },
    )

    assert to_jsonable(command) == {
        "type": "submit_prompt_response",
        "run_id": "run-123",
        "timestamp": "2026-05-12T10:00:05+00:00",
        "payload": {
            "prompt_id": "prompt-1",
            "value": True,
        },
    }


def test_prompt_request_serializes_with_supported_v1_fields():
    prompt = PromptRequest(
        prompt_id="prompt-1",
        prompt_type="confirm",
        message="Do you want to continue?",
        default=True,
        options=[
            PromptOption(
                id="opt-1",
                label="Main",
                value="main",
                description="Default branch",
            )
        ],
    )

    assert to_jsonable(prompt) == {
        "prompt_id": "prompt-1",
        "prompt_type": "confirm",
        "message": "Do you want to continue?",
        "default": True,
        "required": True,
        "options": [
            {
                "id": "opt-1",
                "label": "Main",
                "value": "main",
                "description": "Default branch",
            }
        ],
    }


def test_run_result_serializes_to_v1_terminal_snapshot_shape():
    result = RunResult(
        run_id="run-123",
        workflow_name="demo-workflow",
        status="completed",
        steps=[
            RunStepResult(
                id="check_status",
                title="Check Status",
                status="success",
                plugin="git",
                outputs=[
                    OutputPayload(
                        format="markdown",
                        title="Repository Status",
                        content="## Clean working tree",
                    )
                ],
            )
        ],
        result=OutputPayload(
            format="markdown",
            title="Final Summary",
            content="# Done",
        ),
        diagnostics={
            "result_message": "Workflow completed successfully",
        },
    )

    assert to_jsonable(result) == {
        "run_id": "run-123",
        "workflow_name": "demo-workflow",
        "status": "completed",
        "steps": [
            {
                "id": "check_status",
                "title": "Check Status",
                "status": "success",
                "plugin": "git",
                "error": None,
                "outputs": [
                    {
                        "format": "markdown",
                        "title": "Repository Status",
                        "content": "## Clean working tree",
                        "metadata": {},
                    }
                ],
                "metadata": {},
            }
        ],
        "result": {
            "format": "markdown",
            "title": "Final Summary",
            "content": "# Done",
            "metadata": {},
        },
        "diagnostics": {
            "result_message": "Workflow completed successfully",
        },
    }
