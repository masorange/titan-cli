"""Structured prompt models for UI-agnostic interactions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class PromptOption:
    """Single option shown in a structured prompt."""

    id: str
    label: str
    description: Optional[str] = None
    value: Any = None


@dataclass(slots=True)
class PromptRequest:
    """Prompt emitted by a workflow run and resolved by a UI client."""

    prompt_id: str
    kind: str
    message: str
    default: Any = None
    options: list[PromptOption] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PromptResponse:
    """Response submitted by a client for a pending prompt."""

    prompt_id: str
    value: Any

