"""Workflow application service for backend-oriented execution."""

from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path
from queue import Empty, Queue
from typing import Optional
import uuid as uuid_module

from titan_cli.application.models.events import RunEvent
from titan_cli.application.models.prompts import PromptRequest, PromptResponse
from titan_cli.application.models.requests import (
    StartWorkflowRequest,
    SubmitPromptResponseRequest,
)
from titan_cli.application.models.responses import (
    StartWorkflowResponse,
    WorkflowDetail,
    WorkflowRunState,
    WorkflowStepSummary,
    WorkflowSummary,
)
from titan_cli.application.runtime.event_bus import EventBus
from titan_cli.application.runtime.run_session import RunSession
from titan_cli.application.runtime.run_store import RunStore
from titan_cli.core.config import TitanConfig
from titan_cli.core.secrets import SecretManager
from titan_cli.engine.builder import WorkflowContextBuilder
from titan_cli.engine.interaction.headless import HeadlessInteractionPort
from titan_cli.engine.results import is_error
from titan_cli.engine.workflow_executor import WorkflowExecutor

_CONFIG_CWD_LOCK = threading.Lock()


class PromptRequestedError(BaseException):
    """Raised when workflow execution requires a structured prompt response."""

    def __init__(self, prompt: PromptRequest) -> None:
        super().__init__(prompt.message)
        self.prompt = prompt


class RunInteractionPort(HeadlessInteractionPort):
    """Headless interaction port that mirrors output into run events."""

    def __init__(
        self,
        service: "WorkflowService",
        session: RunSession,
        queued_prompt_responses: Optional[list[object]] = None,
    ) -> None:
        super().__init__()
        self._service = service
        self._session = session
        self._queued_prompt_responses = queued_prompt_responses or []

    def step_output(self, text: str) -> None:
        super().step_output(text)
        self._service._append_event(
            self._session,
            "run_output",
            {"text": text},
        )

    def markdown(self, markdown_text: str) -> None:
        self.messages.append(("markdown", markdown_text))
        self._service._append_event(
            self._session,
            "run_markdown",
            {"text": markdown_text},
        )

    def begin_step(self, step_name: str) -> None:
        super().begin_step(step_name)
        self._service._append_event(
            self._session,
            "step_started",
            {"step_name": step_name},
        )

    def end_step(self, result_type: str) -> None:
        super().end_step(result_type)
        self._service._append_event(
            self._session,
            "step_finished",
            {"result": result_type},
        )

    def confirm(self, prompt_id: str, message: str, default: bool = False) -> bool:
        value = self._request_prompt(
            kind="confirm",
            prompt_id=prompt_id,
            message=message,
            default=default,
        )
        return bool(value)

    def input_text(
        self,
        prompt_id: str,
        message: str,
        default: str | None = None,
    ) -> str:
        value = self._request_prompt(
            kind="text",
            prompt_id=prompt_id,
            message=message,
            default=default,
        )
        return "" if value is None else str(value)

    def multiline_text(
        self,
        prompt_id: str,
        message: str,
        default: str | None = None,
    ) -> str:
        value = self._request_prompt(
            kind="multiline",
            prompt_id=prompt_id,
            message=message,
            default=default,
        )
        return "" if value is None else str(value)

    def _request_prompt(
        self,
        kind: str,
        prompt_id: str,
        message: str,
        default: object = None,
    ) -> object:
        prompt = PromptRequest(
            prompt_id=f"{prompt_id}-{uuid_module.uuid4()}",
            kind=kind,
            message=message,
            default=default,
        )
        if self._queued_prompt_responses:
            value = self._queued_prompt_responses.pop(0)
            self._service._record_prompt_answer(self._session, prompt, value)
            return value

        self._session.pending_prompt = prompt
        self._service._append_event(
            self._session,
            "prompt_requested",
            {
                "prompt_id": prompt.prompt_id,
                "kind": prompt.kind,
                "message": prompt.message,
                "default": prompt.default,
            },
        )
        raise PromptRequestedError(prompt)


class WorkflowService:
    """Facade for listing and starting workflows independently of any UI."""

    def __init__(
        self,
        config: TitanConfig,
        run_store: Optional[RunStore] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._config = config
        self._run_store = run_store or RunStore()
        self._event_bus = event_bus or EventBus()

    def list_workflows(self, project_path: Optional[str] = None) -> list[WorkflowSummary]:
        """Return available workflows from the active registry."""
        config = self._config_for_project_path(project_path)
        summaries: list[WorkflowSummary] = []
        for workflow in config.workflows.discover():
            summaries.append(
                WorkflowSummary(
                    name=workflow.name,
                    description=workflow.description,
                    source=workflow.source,
                )
        )
        return summaries

    def describe_workflow(
        self,
        workflow_name: str,
        project_path: Optional[str] = None,
    ) -> WorkflowDetail | None:
        """Return resolved workflow metadata, including inherited and hook steps."""
        config = self._config_for_project_path(project_path)
        workflow = config.workflows.get_workflow(workflow_name)
        if workflow is None:
            return None

        return WorkflowDetail(
            name=workflow.name,
            description=workflow.description,
            source=workflow.source,
            params=dict(workflow.params),
            steps=[
                self._step_summary_from_dict(step)
                for step in workflow.steps
            ],
        )

    def start_workflow(self, request: StartWorkflowRequest) -> StartWorkflowResponse:
        """Create and execute a workflow run."""
        run_id = str(uuid.uuid4())
        session = RunSession(
            run_id=run_id,
            workflow_name=request.workflow_name,
            status="created",
            metadata={
                "params": request.params,
                "prompt_responses": list(request.prompt_responses),
                "project_path": request.project_path,
                "interaction_mode": request.interaction_mode,
            },
        )
        self._append_event(
            session,
            "workflow_run_created",
            {"workflow_name": request.workflow_name},
        )
        self._run_store.save(session)
        self._execute_run(session, request)
        return StartWorkflowResponse(
            run_id=run_id,
            status=session.status,
            events=list(session.events),
            pending_prompt=session.pending_prompt,
        )

    def get_run(self, run_id: str) -> WorkflowRunState | None:
        """Return the current state for a run id."""
        session = self._run_store.get(run_id)
        if not session:
            return None
        return WorkflowRunState(
            run_id=session.run_id,
            workflow_name=session.workflow_name,
            status=session.status,
            result_message=session.result_message,
            events=list(session.events),
            pending_prompt=session.pending_prompt,
            prompt_history=list(session.prompt_history),
            metadata=dict(session.metadata),
        )

    def stream_events(
        self,
        run_id: str,
        replay: bool = True,
        timeout_seconds: float = 30.0,
    ):
        """Yield run events, replaying known events first and then streaming new ones."""
        session = self._run_store.get(run_id)
        if session is None:
            return

        if replay:
            for event in session.events:
                yield event

        terminal_statuses = {"completed", "failed"}
        if session.status in terminal_statuses:
            return

        queue: Queue[RunEvent] = Queue()

        def _on_event(event: RunEvent) -> None:
            queue.put(event)

        self._event_bus.subscribe(run_id, _on_event)
        try:
            while True:
                try:
                    event = queue.get(timeout=timeout_seconds)
                except Empty:
                    break
                yield event
                current = self._run_store.get(run_id)
                if current and current.status in terminal_statuses:
                    break
        finally:
            self._event_bus.unsubscribe(run_id, _on_event)

    def submit_prompt_response(
        self,
        request: SubmitPromptResponseRequest,
    ) -> WorkflowRunState | None:
        """Store a response for a pending prompt and resume execution."""
        session = self._run_store.get(request.run_id)
        if not session or not session.pending_prompt:
            return self.get_run(request.run_id)

        if session.pending_prompt.prompt_id != request.prompt_id:
            return self.get_run(request.run_id)

        self._record_prompt_answer(session, session.pending_prompt, request.value)
        session.metadata.setdefault("prompt_responses", [])
        session.metadata["prompt_responses"].append(request.value)
        session.status = "running"
        self._append_event(
            session,
            "workflow_run_resumed",
            {"prompt_id": request.prompt_id},
        )
        self._execute_run(session, self._request_from_session(session))
        self._run_store.save(session)
        return self.get_run(request.run_id)

    def _append_event(
        self,
        session: RunSession,
        event_type: str,
        payload: dict,
    ) -> RunEvent:
        """Append, persist, and publish a run event."""
        event = RunEvent(type=event_type, run_id=session.run_id, payload=payload)
        session.events.append(event)
        self._run_store.save(session)
        self._event_bus.publish(event)
        return event

    def _build_context(
        self,
        session: RunSession,
        request: StartWorkflowRequest,
        config: TitanConfig,
    ):
        """Build execution context mirroring the current TUI flow."""
        workspace_path = Path(request.project_path) if request.project_path else config.project_root
        secrets = SecretManager(project_path=workspace_path)
        ctx_builder = WorkflowContextBuilder(
            plugin_registry=config.registry,
            secrets=secrets,
            ai_config=config.config.ai,
        )
        ctx_builder.with_ai()

        for plugin_name in config.registry.list_installed():
            plugin = config.registry.get_plugin(plugin_name)
            if not plugin:
                continue

            if hasattr(ctx_builder, f"with_{plugin_name}"):
                try:
                    client = plugin.get_client()
                    getattr(ctx_builder, f"with_{plugin_name}")(client)
                except Exception:
                    pass

            try:
                managers = plugin.get_workflow_managers(project_root=workspace_path)
                if managers is not None:
                    ctx_builder.with_plugin_managers(plugin_name, managers)
            except Exception:
                pass

        ctx = ctx_builder.build()
        ctx.interaction = RunInteractionPort(
            self,
            session,
            queued_prompt_responses=list(request.prompt_responses),
        )
        # Many existing plugin steps still call ctx.textual.* directly. In
        # headless runs, expose the same surface through the interaction port so
        # the Swift UI can drive Titan without requiring the Textual TUI.
        ctx.textual = ctx.interaction
        ctx.data.update(request.params)
        ctx.data.setdefault("project_root", str(workspace_path))
        ctx.data.setdefault("cwd", str(workspace_path))
        return ctx

    def _request_from_session(self, session: RunSession) -> StartWorkflowRequest:
        """Rebuild the execution request from persisted run session metadata."""
        return StartWorkflowRequest(
            workflow_name=session.workflow_name,
            params=dict(session.metadata.get("params", {})),
            prompt_responses=list(session.metadata.get("prompt_responses", [])),
            project_path=session.metadata.get("project_path"),
            interaction_mode=session.metadata.get("interaction_mode", "headless"),
        )

    def _execute_run(self, session: RunSession, request: StartWorkflowRequest) -> None:
        """Execute a workflow synchronously and update run state."""
        session.status = "running"
        self._append_event(
            session,
            "workflow_run_started",
            {"workflow_name": request.workflow_name},
        )

        config = self._config_for_project_path(request.project_path)
        workflow = config.workflows.get_workflow(request.workflow_name)
        if workflow is None:
            session.status = "failed"
            session.result_message = f"Workflow '{request.workflow_name}' not found."
            self._append_event(
                session,
                "workflow_run_failed",
                {"message": session.result_message},
            )
            return

        try:
            ctx = self._build_context(session, request, config)
            executor = WorkflowExecutor(
                plugin_registry=config.registry,
                workflow_registry=config.workflows,
            )
            result = executor.execute(workflow, ctx, params_override=request.params)
            session.metadata.update(ctx.data)

            if is_error(result):
                session.status = "failed"
                session.result_message = result.message
                self._append_event(
                    session,
                    "workflow_run_failed",
                    {"message": result.message},
                )
                return

            session.status = "completed"
            session.result_message = result.message
            self._append_event(
                session,
                "workflow_run_completed",
                {
                    "message": result.message,
                    "metadata": result.metadata or {},
                },
            )
        except PromptRequestedError as prompt_exc:
            session.status = "waiting_for_input"
            session.pending_prompt = prompt_exc.prompt
            session.result_message = prompt_exc.prompt.message
            self._run_store.save(session)
        except Exception as exc:
            session.status = "failed"
            session.result_message = str(exc)
            self._append_event(
                session,
                "workflow_run_failed",
                {
                    "message": str(exc),
                    "error_type": type(exc).__name__,
                },
            )

    def _config_for_project_path(self, project_path: Optional[str]) -> TitanConfig:
        """Create a workspace-specific config when a project path is provided."""
        if not project_path:
            return self._config

        workspace_path = Path(project_path).expanduser().resolve()
        registry = self._config.registry.__class__()

        with _CONFIG_CWD_LOCK:
            previous_cwd = Path.cwd()
            try:
                os.chdir(workspace_path)
                return TitanConfig(registry=registry)
            finally:
                os.chdir(previous_cwd)

    def _record_prompt_answer(
        self,
        session: RunSession,
        prompt: PromptRequest,
        value: object,
    ) -> None:
        """Persist prompt response and emit lifecycle event."""
        response = PromptResponse(prompt_id=prompt.prompt_id, value=value)
        session.prompt_history.append(response)
        session.pending_prompt = None
        self._append_event(
            session,
            "prompt_answered",
            {
                "prompt_id": prompt.prompt_id,
                "value": value,
            },
        )

    def _step_summary_from_dict(self, step: dict) -> WorkflowStepSummary:
        """Normalize resolved workflow step dictionaries for native clients."""
        return WorkflowStepSummary(
            id=step.get("id"),
            name=step.get("name"),
            plugin=step.get("plugin"),
            step=step.get("step"),
            command=step.get("command"),
            workflow=step.get("workflow"),
            hook=step.get("hook"),
            requires=list(step.get("requires") or []),
            on_error=step.get("on_error", "fail"),
            params=dict(step.get("params") or {}),
        )
