from unittest.mock import MagicMock
from unittest.mock import patch

from titan_cli.application.models.requests import StartWorkflowRequest
from titan_cli.application.models.requests import SubmitPromptResponseRequest
from titan_cli.application.runtime.status import RunSessionStatus
from titan_cli.application.services.workflow_service import WorkflowService
from titan_cli.core.workflows.workflow_sources import WorkflowInfo
from titan_cli.engine.results import Error, Success


def test_list_workflows_maps_registry_discovery():
    config = MagicMock()
    config.workflows.discover.return_value = [
        WorkflowInfo(
            name="demo",
            description="Demo workflow",
            source="project",
            path=MagicMock(),
        )
    ]

    service = WorkflowService(config=config)
    workflows = service.list_workflows()

    assert len(workflows) == 1
    assert workflows[0].name == "demo"
    assert workflows[0].description == "Demo workflow"
    assert workflows[0].source == "project"


def test_start_workflow_creates_run_state():
    config = MagicMock()
    config.workflows.discover.return_value = []
    config.project_root = MagicMock()
    config.registry.list_installed.return_value = []
    service = WorkflowService(config=config)

    response = service.start_workflow(StartWorkflowRequest(workflow_name="demo"))
    run = service.get_run(response.run_id)

    assert response.status == RunSessionStatus.FAILED
    assert run is not None
    assert run.workflow_name == "demo"
    assert run.status == RunSessionStatus.FAILED
    assert run.events[0].type == "run_started"
    assert run.events[-1].type == "run_failed"


@patch("titan_cli.application.services.workflow_service.SecretManager")
@patch("titan_cli.application.services.workflow_service.WorkflowExecutor")
def test_start_workflow_executes_successfully(mock_executor_cls, mock_secret_manager_cls):
    config = MagicMock()
    workflow = MagicMock(name="workflow")
    config.workflows.discover.return_value = []
    config.workflows.get_workflow.return_value = workflow
    config.project_root = MagicMock()
    config.registry.list_installed.return_value = []
    config.config.ai = None

    mock_executor = mock_executor_cls.return_value
    mock_executor.execute.return_value = Success("workflow ok", metadata={"done": True})
    mock_secret_manager_cls.return_value = MagicMock()

    service = WorkflowService(config=config)
    response = service.start_workflow(
        StartWorkflowRequest(workflow_name="demo", params={"foo": "bar"})
    )
    run = service.get_run(response.run_id)

    assert run is not None
    assert response.status == RunSessionStatus.COMPLETED
    assert run.status == RunSessionStatus.COMPLETED
    assert run.result_message == "workflow ok"
    assert run.events[0].type == "run_started"
    assert run.events[-1].type == "run_completed"
    mock_executor.execute.assert_called_once()


@patch("titan_cli.application.services.workflow_service.SecretManager")
@patch("titan_cli.application.services.workflow_service.WorkflowExecutor")
def test_start_workflow_marks_failed_when_executor_returns_error(
    mock_executor_cls,
    mock_secret_manager_cls,
):
    config = MagicMock()
    workflow = MagicMock(name="workflow")
    config.workflows.discover.return_value = []
    config.workflows.get_workflow.return_value = workflow
    config.project_root = MagicMock()
    config.registry.list_installed.return_value = []
    config.config.ai = None

    mock_executor = mock_executor_cls.return_value
    mock_executor.execute.return_value = Error("boom")
    mock_secret_manager_cls.return_value = MagicMock()

    service = WorkflowService(config=config)
    response = service.start_workflow(StartWorkflowRequest(workflow_name="demo"))
    run = service.get_run(response.run_id)

    assert run is not None
    assert response.status == RunSessionStatus.FAILED
    assert run.status == RunSessionStatus.FAILED
    assert run.result_message == "boom"
    assert run.events[-1].type == "run_failed"


@patch("titan_cli.application.services.workflow_service.SecretManager")
@patch("titan_cli.application.services.workflow_service.WorkflowExecutor")
def test_start_workflow_waits_for_prompt_when_interaction_is_required(
    mock_executor_cls,
    mock_secret_manager_cls,
):
    config = MagicMock()
    workflow = MagicMock(name="workflow")
    config.workflows.discover.return_value = []
    config.workflows.get_workflow.return_value = workflow
    config.project_root = MagicMock()
    config.registry.list_installed.return_value = []
    config.config.ai = None
    mock_secret_manager_cls.return_value = MagicMock()

    def _execute(_workflow, ctx, params_override=None):
        ctx.interaction.ask_text("Enter value", default="demo")
        return Success("unreachable")

    mock_executor = mock_executor_cls.return_value
    mock_executor.execute.side_effect = _execute

    service = WorkflowService(config=config)
    response = service.start_workflow(StartWorkflowRequest(workflow_name="demo"))
    run = service.get_run(response.run_id)

    assert run is not None
    assert response.status == RunSessionStatus.WAITING_FOR_INPUT
    assert run.status == RunSessionStatus.WAITING_FOR_INPUT
    assert run.pending_prompt is not None
    assert run.pending_prompt.prompt_type == "text"
    assert run.events[-1].type == "prompt_requested"


@patch("titan_cli.application.services.workflow_service.SecretManager")
@patch("titan_cli.application.services.workflow_service.WorkflowExecutor")
def test_start_workflow_consumes_preseeded_prompt_responses(
    mock_executor_cls,
    mock_secret_manager_cls,
):
    config = MagicMock()
    workflow = MagicMock(name="workflow")
    config.workflows.discover.return_value = []
    config.workflows.get_workflow.return_value = workflow
    config.project_root = MagicMock()
    config.registry.list_installed.return_value = []
    config.config.ai = None
    mock_secret_manager_cls.return_value = MagicMock()

    def _execute(_workflow, ctx, params_override=None):
        answer = ctx.interaction.ask_text("Enter value", default="demo")
        assert answer == "seeded-answer"
        return Success("workflow ok")

    mock_executor = mock_executor_cls.return_value
    mock_executor.execute.side_effect = _execute

    service = WorkflowService(config=config)
    response = service.start_workflow(
        StartWorkflowRequest(
            workflow_name="demo",
            prompt_responses=["seeded-answer"],
        )
    )
    run = service.get_run(response.run_id)

    assert run is not None
    assert response.status == RunSessionStatus.COMPLETED
    assert run.pending_prompt is None
    assert len(run.prompt_history) == 1
    assert run.prompt_history[0].value == "seeded-answer"
    assert not any(event.type == "prompt_answered" for event in run.events)


@patch("titan_cli.application.services.workflow_service.SecretManager")
@patch("titan_cli.application.services.workflow_service.WorkflowExecutor")
def test_start_workflow_exposes_markdown_events_in_headless_runs(
    mock_executor_cls,
    mock_secret_manager_cls,
):
    config = MagicMock()
    workflow = MagicMock(name="workflow")
    config.workflows.discover.return_value = []
    config.workflows.get_workflow.return_value = workflow
    config.project_root = MagicMock()
    config.registry.list_installed.return_value = []
    config.config.ai = None
    mock_secret_manager_cls.return_value = MagicMock()

    def _execute(_workflow, ctx, params_override=None):
        ctx.textual.markdown("## AI Analysis\n\nLooks good.")
        return Success("workflow ok")

    mock_executor = mock_executor_cls.return_value
    mock_executor.execute.side_effect = _execute

    service = WorkflowService(config=config)
    response = service.start_workflow(StartWorkflowRequest(workflow_name="demo"))
    run = service.get_run(response.run_id)

    assert response.status == RunSessionStatus.COMPLETED
    assert run is not None
    assert any(event.type == "output_emitted" for event in run.events)
    assert not any(
        event.type == "run_failed"
        and "markdown" in str(event.payload.get("message", ""))
        for event in run.events
    )


@patch("titan_cli.application.services.workflow_service.SecretManager")
@patch("titan_cli.application.services.workflow_service.WorkflowExecutor")
def test_submit_prompt_response_resumes_run(
    mock_executor_cls,
    mock_secret_manager_cls,
):
    config = MagicMock()
    workflow = MagicMock(name="workflow")
    config.workflows.discover.return_value = []
    config.workflows.get_workflow.return_value = workflow
    config.project_root = MagicMock()
    config.registry.list_installed.return_value = []
    config.config.ai = None
    mock_secret_manager_cls.return_value = MagicMock()

    state = {"calls": 0}

    def _execute(_workflow, ctx, params_override=None):
        state["calls"] += 1
        if state["calls"] == 1:
            ctx.interaction.ask_text("Enter value", default="demo")
            return Success("unreachable")

        answer = ctx.interaction.ask_text("Enter value", default="demo")
        assert answer == "hello"
        return Success("workflow ok")

    mock_executor = mock_executor_cls.return_value
    mock_executor.execute.side_effect = _execute

    service = WorkflowService(config=config)
    response = service.start_workflow(StartWorkflowRequest(workflow_name="demo"))
    waiting = service.get_run(response.run_id)

    assert waiting is not None
    assert waiting.status == RunSessionStatus.WAITING_FOR_INPUT
    assert waiting.pending_prompt is not None

    updated = service.submit_prompt_response(
        SubmitPromptResponseRequest(
            run_id=response.run_id,
            prompt_id=waiting.pending_prompt.prompt_id,
            value="hello",
        )
    )

    assert updated is not None
    assert updated.status == RunSessionStatus.COMPLETED
    assert updated.pending_prompt is None
    assert updated.prompt_history[-1].value == "hello"
    assert not any(event.type == "workflow_run_resumed" for event in updated.events)
    assert updated.events[-1].type == "run_completed"
    assert state["calls"] == 2
