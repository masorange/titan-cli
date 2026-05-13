"""Workflow application service for backend-oriented execution."""

from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Optional

from titan_cli.application.models.prompts import PromptResponse
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
from titan_cli.application.runtime.status import RunSessionStatus
from titan_cli.core.config import TitanConfig
from titan_cli.core.secrets import SecretManager
from titan_cli.engine.builder import WorkflowContextBuilder
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.interaction.headless import HeadlessInteractionPort
from titan_cli.engine.results import is_error
from titan_cli.engine.workflow_executor import WorkflowExecutor
from titan_cli.ports.protocol import EngineEvent
from titan_cli.ports.protocol import EventType
from titan_cli.ports.protocol import OutputFormat
from titan_cli.ports.protocol import OutputPayload
from titan_cli.ports.protocol import PromptRequest
from titan_cli.ports.protocol import PromptType
from titan_cli.ports.protocol import RunResult
from titan_cli.ports.protocol import RunStatus
from titan_cli.ports.protocol import RunStepResult
from titan_cli.ports.protocol import RunStepStatus
from titan_cli.ports.protocol import StepRef

_CONFIG_CWD_LOCK = threading.Lock()
_TERMINAL_SESSION_STATUSES = {
    RunSessionStatus.COMPLETED,
    RunSessionStatus.FAILED,
    RunSessionStatus.CANCELLED,
}


class PromptRequestedError(BaseException):
    """Raised when workflow execution requires a structured prompt response."""

    def __init__(self, prompt: PromptRequest) -> None:
        super().__init__(prompt.message)
        self.prompt = prompt


class RunInteractionPort(HeadlessInteractionPort):
    """Headless interaction port that mirrors workflow activity into V1 events."""

    def __init__(
        self,
        service: "WorkflowService",
        session: RunSession,
        ctx: WorkflowContext,
        queued_prompt_responses: Optional[list[object]] = None,
    ) -> None:
        super().__init__()
        self._service = service
        self._session = session
        self._ctx = ctx
        self._queued_prompt_responses = queued_prompt_responses or []

    def step_output(self, text: str) -> None:
        super().step_output(text)
        self._service._append_event(
            self._session,
            EventType.OUTPUT_EMITTED,
            {
                "step": self._step_ref(),
                "output": OutputPayload(
                    format=OutputFormat.TEXT,
                    content=text,
                ),
            },
        )

    def markdown(self, markdown_text: str) -> None:
        self.messages.append(("markdown", markdown_text))
        self._service._append_event(
            self._session,
            EventType.OUTPUT_EMITTED,
            {
                "step": self._step_ref(),
                "output": OutputPayload(
                    format=OutputFormat.MARKDOWN,
                    title="Markdown output",
                    content=markdown_text,
                ),
            },
        )

    def begin_step(self, step_name: str) -> None:
        super().begin_step(step_name)
        self._service._append_event(
            self._session,
            EventType.STEP_STARTED,
            {
                "step": self._step_ref(step_name=step_name),
                "plugin": self._ctx.current_step_plugin,
                "step_kind": self._ctx.current_step_kind or "plugin",
            },
        )

    def end_step(self, result_type: str) -> None:
        super().end_step(result_type)
        normalized = self._service._normalize_step_status(result_type)

        if normalized == RunStepStatus.SUCCESS:
            self._service._append_event(
                self._session,
                EventType.STEP_FINISHED,
                {
                    "step": self._step_ref(),
                    "status": RunStepStatus.SUCCESS,
                    "message": result_type,
                    "metadata": {},
                },
            )
            return

        self._service._append_event(
            self._session,
            EventType.STEP_SKIPPED if normalized == RunStepStatus.SKIPPED else EventType.STEP_FAILED,
            {
                "step": self._step_ref(),
                "message": result_type,
            },
        )

    def confirm(self, prompt_id: str, message: str, default: bool = False) -> bool:
        value = self._request_prompt(
            prompt_type=PromptType.CONFIRM,
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
            prompt_type=PromptType.TEXT,
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
            prompt_type=PromptType.MULTILINE,
            prompt_id=prompt_id,
            message=message,
            default=default,
        )
        return "" if value is None else str(value)

    def _request_prompt(
        self,
        prompt_type: PromptType,
        prompt_id: str,
        message: str,
        default: object = None,
    ) -> object:
        full_prompt_id = (
            f"{self._ctx.current_step_id}:{prompt_id}"
            if self._ctx.current_step_id
            else prompt_id
        )
        prompt = PromptRequest(
            prompt_id=full_prompt_id,
            prompt_type=prompt_type,
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
            EventType.PROMPT_REQUESTED,
            {
                "step": self._step_ref(),
                "prompt": prompt,
            },
        )
        raise PromptRequestedError(prompt)

    def _step_ref(self, step_name: Optional[str] = None) -> StepRef:
        return StepRef(
            step_id=self._ctx.current_step_id or "step",
            step_name=step_name or self._ctx.current_step_name or "Step",
            step_index=self._ctx.current_step or 0,
        )


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
            steps=[self._step_summary_from_dict(step) for step in workflow.steps],
        )

    def start_workflow(self, request: StartWorkflowRequest) -> StartWorkflowResponse:
        """Create and execute a workflow run."""
        session = self.create_run(request)
        self._execute_run(session, request)
        return StartWorkflowResponse(
            run_id=session.run_id,
            status=session.status,
            events=list(session.events),
            pending_prompt=session.pending_prompt,
            result=self._result_for_session(session),
        )

    def create_run(self, request: StartWorkflowRequest) -> RunSession:
        """Create and persist a run session before execution starts."""
        session = RunSession(
            run_id=str(uuid.uuid4()),
            workflow_name=request.workflow_name,
            status=RunSessionStatus.CREATED,
            metadata={
                "params": request.params,
                "prompt_responses": list(request.prompt_responses),
                "project_path": request.project_path,
                "interaction_mode": request.interaction_mode,
            },
        )
        self._run_store.save(session)
        return session

    def execute_run(self, session: RunSession, request: StartWorkflowRequest) -> None:
        """Execute a previously created run session."""
        self._execute_run(session, request)

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
            result=self._result_for_session(session),
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

        if session.status in _TERMINAL_SESSION_STATUSES:
            return

        queue: Queue[EngineEvent] = Queue()

        def _on_event(event: EngineEvent) -> None:
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
                if current and current.status in _TERMINAL_SESSION_STATUSES:
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
        session.status = RunSessionStatus.RUNNING
        self._execute_run(session, self._request_from_session(session))
        self._run_store.save(session)
        return self.get_run(request.run_id)

    def cancel_run(self, run_id: str, reason: str = "Run cancelled by user") -> WorkflowRunState | None:
        """Mark a run as cancelled and emit the terminal V1 event."""
        session = self._run_store.get(run_id)
        if not session:
            return None
        if session.status in _TERMINAL_SESSION_STATUSES:
            return self.get_run(run_id)

        session.metadata["cancel_requested"] = reason

        if session.status == RunSessionStatus.WAITING_FOR_INPUT:
            session.pending_prompt = None
            session.status = RunSessionStatus.CANCELLED
            session.result_message = reason
            self._append_event(
                session,
                EventType.RUN_CANCELLED,
                {"message": reason},
            )

        self._run_store.save(session)
        return self.get_run(run_id)

    def _append_event(
        self,
        session: RunSession,
        event_type: EventType,
        payload: dict[str, Any],
    ) -> EngineEvent:
        """Append, persist, and publish a run event."""
        event = EngineEvent(
            type=event_type,
            run_id=session.run_id,
            sequence=len(session.events) + 1,
            payload=payload,
        )
        session.events.append(event)
        self._run_store.save(session)
        self._event_bus.publish(event)
        return event

    def _build_context(
        self,
        session: RunSession,
        request: StartWorkflowRequest,
        config: TitanConfig,
    ) -> WorkflowContext:
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
            ctx,
            queued_prompt_responses=list(request.prompt_responses),
        )
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
        config = self._config_for_project_path(request.project_path)
        workflow = config.workflows.get_workflow(request.workflow_name)

        session.status = RunSessionStatus.RUNNING
        self._append_event(
            session,
            EventType.RUN_STARTED,
            {
                "workflow_name": request.workflow_name,
                "workflow_title": workflow.description if workflow else request.workflow_name,
                "project_path": request.project_path or str(config.project_root),
                "total_steps": self._count_workflow_steps(workflow),
            },
        )

        if workflow is None:
            session.status = RunSessionStatus.FAILED
            session.result_message = f"Workflow '{request.workflow_name}' not found."
            self._append_event(
                session,
                EventType.RUN_FAILED,
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

            cancel_reason = session.metadata.get("cancel_requested")
            if cancel_reason:
                session.status = RunSessionStatus.CANCELLED
                session.result_message = str(cancel_reason)
                self._append_event(
                    session,
                    EventType.RUN_CANCELLED,
                    {"message": str(cancel_reason)},
                )
                return

            if is_error(result):
                session.status = RunSessionStatus.FAILED
                session.result_message = result.message
                self._append_event(
                    session,
                    EventType.RUN_FAILED,
                    {"message": result.message},
                )
                return

            session.status = RunSessionStatus.COMPLETED
            session.result_message = result.message
            self._append_event(
                session,
                EventType.RUN_COMPLETED,
                {
                    "message": result.message,
                    "metadata": result.metadata or {},
                },
            )
        except PromptRequestedError as prompt_exc:
            session.status = RunSessionStatus.WAITING_FOR_INPUT
            session.pending_prompt = prompt_exc.prompt
            session.result_message = prompt_exc.prompt.message
            self._run_store.save(session)
        except Exception as exc:
            session.status = RunSessionStatus.FAILED
            session.result_message = str(exc)
            self._append_event(
                session,
                EventType.RUN_FAILED,
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
        """Persist prompt response without exposing extra non-V1 events."""
        response = PromptResponse(prompt_id=prompt.prompt_id, value=value)
        session.prompt_history.append(response)
        session.pending_prompt = None

    def _result_for_session(self, session: RunSession) -> RunResult | None:
        """Return the terminal RunResult only for terminal session states."""
        if session.status not in _TERMINAL_SESSION_STATUSES:
            return None
        return self._workflow_result_from_session(session)

    def _workflow_result_from_session(self, session: RunSession) -> RunResult:
        """Build the terminal V1 run snapshot from structured run events."""
        steps: list[RunStepResult] = []
        step_by_id: dict[str, RunStepResult] = {}
        final_output: OutputPayload | None = None
        last_step: RunStepResult | None = None

        for event in session.events:
            payload = event.payload

            if event.type == EventType.STEP_STARTED:
                step = payload.get("step")
                if not isinstance(step, StepRef):
                    continue

                current_step = RunStepResult(
                    id=step.step_id,
                    title=step.step_name,
                    status=RunStepStatus.SUCCESS,
                    plugin=self._optional_str(payload.get("plugin")),
                    metadata={
                        key: value
                        for key, value in payload.items()
                        if key not in {"step", "plugin"}
                    },
                )
                steps.append(current_step)
                step_by_id[step.step_id] = current_step
                last_step = current_step
                continue

            step = payload.get("step")
            current_step = self._lookup_step(step_by_id, step)

            if event.type == EventType.STEP_FINISHED:
                if current_step is not None:
                    current_step.status = RunStepStatus.SUCCESS
                continue

            if event.type == EventType.STEP_FAILED:
                if current_step is not None:
                    current_step.status = RunStepStatus.FAILED
                    current_step.error = self._optional_str(payload.get("message"))
                continue

            if event.type == EventType.STEP_SKIPPED:
                if current_step is not None:
                    current_step.status = RunStepStatus.SKIPPED
                continue

            if event.type == EventType.OUTPUT_EMITTED:
                output = payload.get("output")
                if not isinstance(output, OutputPayload):
                    continue
                if current_step is not None:
                    current_step.outputs.append(output)
                final_output = output
                continue

            if event.type == EventType.RUN_FAILED:
                failed_step = current_step or last_step
                if failed_step is not None and failed_step.status == RunStepStatus.SUCCESS:
                    failed_step.status = RunStepStatus.FAILED
                    failed_step.error = self._optional_str(payload.get("message"))

        return RunResult(
            run_id=session.run_id,
            workflow_name=session.workflow_name,
            status=self._normalize_run_status(session.status),
            steps=steps,
            result=final_output,
            diagnostics={
                "result_message": session.result_message,
                "pending_prompt_id": (
                    session.pending_prompt.prompt_id
                    if session.pending_prompt is not None
                    else None
                ),
            },
        )

    def _count_workflow_steps(self, workflow: Any) -> int:
        """Count executable non-hook steps for the run_started payload."""
        if workflow is None:
            return 0
        return len([step for step in workflow.steps if not step.get("hook")])

    def _lookup_step(
        self,
        step_by_id: dict[str, RunStepResult],
        step: object,
    ) -> RunStepResult | None:
        """Resolve a step result from a StepRef payload."""
        if not isinstance(step, StepRef):
            return None
        return step_by_id.get(step.step_id)

    def _normalize_run_status(self, value: RunSessionStatus) -> RunStatus:
        """Return a valid terminal V1 run status."""
        if value == RunSessionStatus.COMPLETED:
            return RunStatus.COMPLETED
        if value == RunSessionStatus.CANCELLED:
            return RunStatus.CANCELLED
        return RunStatus.FAILED

    def _normalize_step_status(self, value: object) -> RunStepStatus:
        """Convert engine result labels into terminal V1 step statuses."""
        raw = str(value or "").lower()
        if raw in {"success", "succeeded", "completed", "done"}:
            return RunStepStatus.SUCCESS
        if raw in {"skip", "skipped"}:
            return RunStepStatus.SKIPPED
        return RunStepStatus.FAILED

    def _optional_str(self, value: object) -> Optional[str]:
        """Return string values while preserving absent metadata as null."""
        if value is None:
            return None
        return str(value)

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
