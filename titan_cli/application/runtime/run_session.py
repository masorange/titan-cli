"""Workflow run session state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from titan_cli.application.models.prompts import PromptResponse
from titan_cli.application.runtime.status import RunSessionStatus
from titan_cli.ports.protocol import EngineEvent
from titan_cli.ports.protocol import PromptRequest


@dataclass
class RunSession:
    """Mutable state for a workflow run."""

    run_id: str
    workflow_name: str
    status: RunSessionStatus = RunSessionStatus.PENDING
    result_message: Optional[str] = None
    events: list[EngineEvent] = field(default_factory=list)
    pending_prompt: Optional[PromptRequest] = None
    prompt_history: list[PromptResponse] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
