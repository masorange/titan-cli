"""Application-layer response models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .events import RunEvent
from .prompts import PromptRequest, PromptResponse


@dataclass(slots=True)
class WorkflowSummary:
    """Compact workflow metadata for listings."""

    name: str
    description: Optional[str] = None
    source: Optional[str] = None


@dataclass(slots=True)
class WorkflowStepSummary:
    """Machine-readable workflow step metadata for native clients."""

    id: Optional[str]
    name: Optional[str]
    plugin: Optional[str] = None
    step: Optional[str] = None
    command: Optional[str] = None
    workflow: Optional[str] = None
    hook: Optional[str] = None
    requires: list[str] = field(default_factory=list)
    on_error: str = "fail"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowDetail:
    """Resolved workflow metadata including steps after inheritance/hooks."""

    name: str
    description: Optional[str]
    source: Optional[str]
    params: dict[str, Any] = field(default_factory=dict)
    steps: list[WorkflowStepSummary] = field(default_factory=list)


@dataclass(slots=True)
class PluginInspection:
    """Machine-readable plugin status for native clients."""

    name: str
    enabled: bool
    installed: bool
    loaded: bool
    available: bool
    version: str = "unknown"
    description: Optional[str] = None
    source: dict[str, Any] = field(default_factory=dict)
    workflows: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass(slots=True)
class KnownPluginSummary:
    """Plugin available for guided installation."""

    name: str
    description: str
    package_name: str
    source: str = "official"
    repo_url: Optional[str] = None
    recommended_ref: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PluginMutationResult:
    """Result returned after mutating plugin configuration."""

    plugin_name: str
    changed: bool
    message: str
    source: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PluginSourcePreview:
    """Preview metadata for a stable community plugin source."""

    repo_url: str
    requested_ref: str
    resolved_commit: str
    package_name: Optional[str]
    version: Optional[str]
    description: Optional[str]
    authors: list[str] = field(default_factory=list)
    titan_entry_points: dict[str, str] = field(default_factory=dict)
    python_dependencies: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectInspection:
    """Complete project snapshot for native clients."""

    name: Optional[str]
    type: Optional[str]
    path: str
    config_path: Optional[str]
    configured: bool
    plugins: list[PluginInspection] = field(default_factory=list)
    workflows: list[WorkflowSummary] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sync_events: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WorkspaceSummary:
    """Workspace exposed to API clients."""

    id: str
    name: str
    path: str
    type: str = "generic"
    configured: bool = False
    capabilities: list[str] = field(default_factory=list)
    source: str = "discovered"


@dataclass(slots=True)
class StartWorkflowResponse:
    """Initial response returned when a workflow run starts."""

    run_id: str
    status: str
    events: list[RunEvent] = field(default_factory=list)
    pending_prompt: Optional[PromptRequest] = None


@dataclass(slots=True)
class WorkflowRunState:
    """Serializable snapshot of a workflow run."""

    run_id: str
    workflow_name: str
    status: str
    result_message: Optional[str] = None
    events: list[RunEvent] = field(default_factory=list)
    pending_prompt: Optional[PromptRequest] = None
    prompt_history: list[PromptResponse] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowOutput:
    """User-facing output produced by a workflow or step."""

    kind: str
    content: str
    title: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowStepResult:
    """Final UI-agnostic state for a single workflow step."""

    id: str
    title: str
    status: str
    plugin: Optional[str] = None
    error: Optional[str] = None
    outputs: list[WorkflowOutput] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowResult:
    """Stable terminal result contract for cross-platform UI clients."""

    run_id: str
    workflow_name: str
    status: str
    steps: list[WorkflowStepResult] = field(default_factory=list)
    result: Optional[WorkflowOutput] = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
