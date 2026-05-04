import json
from datetime import datetime, timezone

from titan_cli.application.models.events import RunEvent
from titan_cli.application.models.responses import (
    WorkflowOutput,
    WorkflowResult,
    WorkflowStepResult,
)
from titan_cli.runtime.output import to_jsonable


def test_workflow_result_contract_serializes_to_snake_case_json():
    result = WorkflowResult(
        run_id="run-1",
        workflow_name="analyze-jira-issues",
        status="completed",
        steps=[
            WorkflowStepResult(
                id="ai_analyze_issue",
                title="AI Analyze Issue",
                status="success",
                plugin="jira",
                outputs=[
                    WorkflowOutput(
                        kind="markdown",
                        title="JIRA Issue Analysis",
                        content="# Analysis\n\nLooks good.",
                    )
                ],
            )
        ],
        result=WorkflowOutput(
            kind="markdown",
            title="Final analysis",
            content="# Final analysis",
        ),
        diagnostics={"stderr_tail": ""},
    )

    payload = to_jsonable(result)

    assert payload == {
        "run_id": "run-1",
        "workflow_name": "analyze-jira-issues",
        "status": "completed",
        "steps": [
            {
                "id": "ai_analyze_issue",
                "title": "AI Analyze Issue",
                "status": "success",
                "plugin": "jira",
                "error": None,
                "outputs": [
                    {
                        "kind": "markdown",
                        "content": "# Analysis\n\nLooks good.",
                        "title": "JIRA Issue Analysis",
                        "metadata": {},
                    }
                ],
                "metadata": {},
            }
        ],
        "result": {
            "kind": "markdown",
            "content": "# Final analysis",
            "title": "Final analysis",
            "metadata": {},
        },
        "diagnostics": {"stderr_tail": ""},
    }
    json.dumps(payload)


def test_run_events_keep_machine_readable_timestamps_and_payloads():
    event = RunEvent(
        type="step_started",
        run_id="run-1",
        timestamp=datetime(2026, 4, 27, 8, 0, tzinfo=timezone.utc),
        payload={
            "step_id": "search_open_issues",
            "step_name": "Search Open Issues",
            "step_index": 1,
            "plugin": "jira",
        },
    )

    assert to_jsonable(event) == {
        "type": "step_started",
        "run_id": "run-1",
        "payload": {
            "step_id": "search_open_issues",
            "step_name": "Search Open Issues",
            "step_index": 1,
            "plugin": "jira",
        },
        "timestamp": "2026-04-27T08:00:00+00:00",
    }
