"""Workflow run session state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from titan_cli.application.models.events import RunEvent
from titan_cli.application.models.prompts import PromptRequest, PromptResponse


@dataclass
class RunSession:
    """Mutable state for a workflow run."""

    run_id: str
    workflow_name: str
    status: str = "pending"
    result_message: Optional[str] = None
    events: list[RunEvent] = field(default_factory=list)
    pending_prompt: Optional[PromptRequest] = None
    prompt_history: list[PromptResponse] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
