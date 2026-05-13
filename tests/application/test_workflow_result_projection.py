from titan_cli.application.runtime.status import RunSessionStatus
from titan_cli.application.runtime.run_session import RunSession
from titan_cli.application.services.workflow_service import WorkflowService
from titan_cli.ports.protocol import EventType
from titan_cli.ports.protocol import OutputPayload
from titan_cli.ports.protocol import StepRef


class EmptyConfig:
    pass


def test_workflow_service_projects_events_into_ui_result():
    service = WorkflowService(config=EmptyConfig())
    session = RunSession(
        run_id="run-1",
        workflow_name="analyze-jira-issues",
        status=RunSessionStatus.COMPLETED,
        result_message="done",
    )

    service._append_event(
        session,
        EventType.RUN_STARTED,
        {"workflow_name": "analyze-jira-issues"},
    )
    service._append_event(
        session,
        EventType.STEP_STARTED,
        {
            "step": StepRef(
                step_id="ai_analyze_issue",
                step_name="AI Analyze Issue",
                step_index=1,
            ),
            "plugin": "jira",
        },
    )
    service._append_event(
        session,
        EventType.OUTPUT_EMITTED,
        {
            "step": StepRef(
                step_id="ai_analyze_issue",
                step_name="AI Analyze Issue",
                step_index=1,
            ),
            "output": OutputPayload(
                format="text",
                content="AI Analysis Results",
            ),
        },
    )
    service._append_event(
        session,
        EventType.OUTPUT_EMITTED,
        {
            "step": StepRef(
                step_id="ai_analyze_issue",
                step_name="AI Analyze Issue",
                step_index=1,
            ),
            "output": OutputPayload(
                format="markdown",
                title="Markdown output",
                content="# JIRA Issue Analysis\n\nLooks good.",
            ),
        },
    )
    service._append_event(
        session,
        EventType.STEP_FINISHED,
        {
            "step": StepRef(
                step_id="ai_analyze_issue",
                step_name="AI Analyze Issue",
                step_index=1,
            ),
            "status": "success",
            "message": "done",
            "metadata": {},
        },
    )
    service._append_event(session, EventType.RUN_COMPLETED, {"message": "done"})

    result = service._workflow_result_from_session(session)

    assert result.run_id == "run-1"
    assert result.workflow_name == "analyze-jira-issues"
    assert result.status == "completed"
    assert len(result.steps) == 1
    assert result.steps[0].id == "ai_analyze_issue"
    assert result.steps[0].title == "AI Analyze Issue"
    assert result.steps[0].status == "success"
    assert result.steps[0].plugin == "jira"
    assert [output.format for output in result.steps[0].outputs] == ["text", "markdown"]
    assert result.result is not None
    assert result.result.format == "markdown"


def test_workflow_service_marks_running_step_failed_from_workflow_failure():
    service = WorkflowService(config=EmptyConfig())
    session = RunSession(
        run_id="run-2",
        workflow_name="demo",
        status=RunSessionStatus.FAILED,
        result_message="boom",
    )

    service._append_event(
        session,
        EventType.STEP_STARTED,
        {
            "step": StepRef(
                step_id="explode",
                step_name="Explode",
                step_index=1,
            )
        },
    )
    service._append_event(session, EventType.RUN_FAILED, {"message": "boom"})

    result = service._workflow_result_from_session(session)

    assert result.steps[0].status == "failed"
    assert result.steps[0].error == "boom"
