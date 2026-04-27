"""Application-layer request models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class StartWorkflowRequest:
    """Request to start a workflow run."""

    workflow_name: str
    params: dict[str, Any] = field(default_factory=dict)
    prompt_responses: list[Any] = field(default_factory=list)
    project_path: Optional[str] = None
    interaction_mode: str = "headless"


@dataclass(slots=True)
class SubmitPromptResponseRequest:
    """Request to answer a pending workflow prompt."""

    run_id: str
    prompt_id: str
    value: Any
