from titan_cli.application.runtime.run_session import RunSession
from titan_cli.application.services.workflow_service import WorkflowService


class EmptyConfig:
    pass


def test_workflow_service_projects_events_into_ui_result():
    service = WorkflowService(config=EmptyConfig())
    session = RunSession(
        run_id="run-1",
        workflow_name="analyze-jira-issues",
        status="completed",
        result_message="done",
    )

    service._append_event(
        session,
        "workflow_run_started",
        {"workflow_name": "analyze-jira-issues"},
    )
    service._append_event(
        session,
        "step_started",
        {"step_name": "AI Analyze Issue", "plugin": "jira"},
    )
    service._append_event(session, "run_output", {"text": "AI Analysis Results"})
    service._append_event(
        session,
        "run_markdown",
        {"text": "# JIRA Issue Analysis\n\nLooks good."},
    )
    service._append_event(session, "step_finished", {"result": "success"})
    service._append_event(session, "workflow_run_completed", {"message": "done"})

    result = service._workflow_result_from_session(session)

    assert result.run_id == "run-1"
    assert result.workflow_name == "analyze-jira-issues"
    assert result.status == "completed"
    assert len(result.steps) == 1
    assert result.steps[0].id == "ai_analyze_issue"
    assert result.steps[0].title == "AI Analyze Issue"
    assert result.steps[0].status == "success"
    assert result.steps[0].plugin == "jira"
    assert [output.kind for output in result.steps[0].outputs] == ["text", "markdown"]
    assert result.result is not None
    assert result.result.kind == "markdown"


def test_workflow_service_marks_running_step_failed_from_workflow_failure():
    service = WorkflowService(config=EmptyConfig())
    session = RunSession(
        run_id="run-2",
        workflow_name="demo",
        status="failed",
        result_message="boom",
    )

    service._append_event(session, "step_started", {"step_name": "Explode"})
    service._append_event(session, "workflow_run_failed", {"message": "boom"})

    result = service._workflow_result_from_session(session)

    assert result.steps[0].status == "failed"
    assert result.steps[0].error == "boom"
