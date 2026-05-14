"""Titan protocol dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Optional


class EventType(StrEnum):
    """Supported outbound event names for the V1 protocol."""

    RUN_STARTED = "run_started"
    STEP_STARTED = "step_started"
    OUTPUT_EMITTED = "output_emitted"
    PROMPT_REQUESTED = "prompt_requested"
    STEP_FINISHED = "step_finished"
    STEP_FAILED = "step_failed"
    STEP_SKIPPED = "step_skipped"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    RUN_RESULT_EMITTED = "run_result_emitted"


class CommandType(StrEnum):
    """Supported inbound command names for the V1 protocol."""

    SUBMIT_PROMPT_RESPONSE = "submit_prompt_response"
    CANCEL_RUN = "cancel_run"


class PromptType(StrEnum):
    """Prompt kinds defined by the V1 protocol."""

    CONFIRM = "confirm"
    TEXT = "text"
    MULTILINE = "multiline"
    SELECT_ONE = "select_one"
    MULTI_SELECT = "multi_select"
    SECRET = "secret"


class OutputFormat(StrEnum):
    """Semantic output formats defined by the V1 protocol."""

    TEXT = "text"
    MARKDOWN = "markdown"
    TABLE = "table"
    DIFF = "diff"
    WARNING = "warning"
    ERROR = "error"
    JSON = "json"


class RunStatus(StrEnum):
    """Terminal run states supported by V1."""

    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStepStatus(StrEnum):
    """Terminal step states supported by V1."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True)
class StepRef:
    """Shared step identity used across step-scoped protocol messages."""

    step_id: str
    step_name: str
    step_index: int


@dataclass(slots=True)
class OutputPayload:
    """Semantic output emitted by the engine."""

    format: OutputFormat
    content: str
    title: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PromptOption:
    """Option used by selection-oriented prompt types."""

    id: str
    label: str
    value: Any = None
    description: Optional[str] = None


@dataclass(slots=True)
class PromptRequest:
    """Structured prompt request exposed through the V1 protocol."""

    prompt_id: str
    prompt_type: PromptType
    message: str
    default: Any = None
    required: bool = True
    options: list[PromptOption] = field(default_factory=list)


@dataclass(slots=True)
class EngineEvent:
    """Outbound event emitted by a live workflow run."""

    type: EventType
    run_id: str
    sequence: int
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class EngineCommand:
    """Inbound command sent by an adapter to a live workflow run."""

    type: CommandType
    run_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class RunStepResult:
    """Terminal summary for a single step in a run result."""

    id: str
    title: str
    status: RunStepStatus
    plugin: Optional[str] = None
    error: Optional[str] = None
    outputs: list[OutputPayload] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RunResult:
    """Terminal-only run snapshot returned by the V1 protocol."""

    run_id: str
    workflow_name: str
    status: RunStatus
    steps: list[RunStepResult] = field(default_factory=list)
    result: Optional[OutputPayload] = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
