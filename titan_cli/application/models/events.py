"""Structured execution events for multi-UI workflow runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(slots=True)
class RunEvent:
    """Structured event emitted during a workflow run."""

    type: str
    run_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class WorkflowLifecycleEvent(RunEvent):
    """Lifecycle event for workflow execution."""

    workflow_name: Optional[str] = None


@dataclass(slots=True)
class StepLifecycleEvent(RunEvent):
    """Lifecycle event for workflow steps."""

    step_id: Optional[str] = None
    step_name: Optional[str] = None
    step_index: Optional[int] = None

