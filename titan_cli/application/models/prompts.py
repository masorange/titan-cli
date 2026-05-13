"""Application prompt helpers not exposed as V1 protocol contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class PromptResponse:
    """Response submitted by a client for a pending prompt."""

    prompt_id: str
    value: Any
