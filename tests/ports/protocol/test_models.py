from datetime import datetime, timezone

from titan_cli.ports.protocol import EngineCommand
from titan_cli.ports.protocol import ContentBlock
from titan_cli.ports.protocol import ContentBlockType
from titan_cli.ports.protocol import DiffPresentationType
from titan_cli.ports.protocol import EngineEvent
from titan_cli.ports.protocol import ItemReviewEditState
from titan_cli.ports.protocol import ItemReviewItem
from titan_cli.ports.protocol import InteractionOption
from titan_cli.ports.protocol import InteractionRequest
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


def test_diff_presentation_type_serializes_as_string_value():
    payload = OutputPayload(
        format="diff",
        title="Diff summary",
        content="diff --git a/foo b/foo",
        metadata={"type": DiffPresentationType.SUMMARY},
    )

    assert to_jsonable(payload) == {
        "format": "diff",
        "title": "Diff summary",
        "content": "diff --git a/foo b/foo",
        "metadata": {"type": "summary"},
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


def test_interaction_request_serializes_with_first_slice_fields():
    interaction = InteractionRequest(
        interaction_id="select-cli:select-cli",
        interaction_type="option_list",
        message="Which AI CLI do you want to use for this PR review?",
        state={
            "options": [
                InteractionOption(
                    id="claude",
                    label="Claude",
                    value="claude",
                    description="Anthropic's Claude AI",
                )
            ],
            "allow_empty": False,
        },
    )

    assert to_jsonable(interaction) == {
        "interaction_id": "select-cli:select-cli",
        "interaction_type": "option_list",
        "message": "Which AI CLI do you want to use for this PR review?",
        "state": {
            "options": [
                {
                    "id": "claude",
                    "label": "Claude",
                    "value": "claude",
                    "description": "Anthropic's Claude AI",
                    "badges": [],
                }
            ],
            "allow_empty": False,
        },
        "actions": [],
        "metadata": {},
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


def test_item_review_interaction_serializes_with_content_blocks():
    interaction = InteractionRequest(
        interaction_id="validate_actions:review-item-0",
        interaction_type="item_review",
        message="Review the proposed action and choose what to do next.",
        state={
            "review_id": "validate-review-actions",
            "items": [
                ItemReviewItem(
                    id="new_comment:0",
                    title="Comment 1 of 2",
                    status="important",
                    content_blocks=[
                        ContentBlock(
                            type=ContentBlockType.TEXT,
                            title="Proposed action",
                            content="This may fail when the response is empty.",
                        )
                    ],
                    editable=True,
                )
            ],
            "initial_index": 0,
            "allowed_actions": ["approve", "edit", "skip", "exit"],
            "edit": ItemReviewEditState(
                enabled=True,
                label="Edit review comment",
            ),
            "metadata": {},
        },
    )

    assert to_jsonable(interaction) == {
        "interaction_id": "validate_actions:review-item-0",
        "interaction_type": "item_review",
        "message": "Review the proposed action and choose what to do next.",
        "state": {
            "review_id": "validate-review-actions",
            "items": [
                {
                    "id": "new_comment:0",
                    "title": "Comment 1 of 2",
                    "status": "important",
                    "content_blocks": [
                    {
                        "type": "text",
                        "title": "Proposed action",
                        "content": "This may fail when the response is empty.",
                        "variant": "default",
                        "metadata": {},
                    }
                ],
                    "editable": True,
                    "metadata": {},
                }
            ],
            "initial_index": 0,
            "allowed_actions": ["approve", "edit", "skip", "exit"],
            "edit": {
                "enabled": True,
                "label": "Edit review comment",
                "initial_value": None,
            },
            "metadata": {},
        },
        "actions": [],
        "metadata": {},
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


def test_engine_event_serializes_run_result_payload_for_terminal_stream_shape():
    event = EngineEvent(
        type="run_result_emitted",
        run_id="run-123",
        sequence=8,
        timestamp=datetime(2026, 5, 12, 10, 0, 8, tzinfo=timezone.utc),
        payload={
            "run_result": RunResult(
                run_id="run-123",
                workflow_name="demo-workflow",
                status="completed",
                result=OutputPayload(
                    format="markdown",
                    title="Final Summary",
                    content="# Done",
                ),
                diagnostics={"result_message": "Workflow completed successfully"},
            )
        },
    )

    assert to_jsonable(event) == {
        "type": "run_result_emitted",
        "run_id": "run-123",
        "sequence": 8,
        "timestamp": "2026-05-12T10:00:08+00:00",
        "payload": {
            "run_result": {
                "run_id": "run-123",
                "workflow_name": "demo-workflow",
                "status": "completed",
                "steps": [],
                "result": {
                    "format": "markdown",
                    "title": "Final Summary",
                    "content": "# Done",
                    "metadata": {},
                },
                "diagnostics": {"result_message": "Workflow completed successfully"},
            }
        },
    }
