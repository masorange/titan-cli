"""
Data models for the AI execution routing layer.

Request/result/policy/decision shapes. Per D-001, AIExecutionResult
mirrors ClientResult's success/error shape (titan_cli/core/result.py) so
existing ClientSuccess/ClientError pattern-matching habits transfer, but it
is its own type, not a subclass or alias of ClientResult.
"""

from dataclasses import dataclass, field
from typing import Generic, List, Optional, Set, TypeVar

from .enums import AICapability, AIProviderType

T = TypeVar("T")


@dataclass
class AIExecutionRequest:
    """
    A single step's request for AI execution.

    `task` is a plain string (not `AITask`) so community plugins can use
    their own task identifiers as routing/preference-persistence keys - see
    `AITask` in `enums.py` for the recommended vocabulary official plugins
    should reuse. `task` is never sent to the model; only `prompt` is.
    """

    task: str
    prompt: str
    capabilities: Set[AICapability] = field(default_factory=set)
    mode: str = "auto"
    interaction: str = "auto"
    output_contract: Optional[str] = None
    policy_scope: str = "workflow"


@dataclass
class AIRoutePolicy:
    """
    Workflow/step-declared routing policy (mirrors the YAML `ai:` block).

    `strict=True` means only providers satisfying `capabilities` may be used,
    with no silent fallback outside that set. Enforcement ships in later
    phases; the field exists from now per decision O-003.
    """

    task: str
    capabilities: Set[AICapability] = field(default_factory=set)
    preferred: List[AIProviderType] = field(default_factory=list)
    strict: bool = False
    remember: str = "ask"  # "ask" | "always" | "never"


@dataclass
class AIRouteDecision:
    """The provider the router resolved a request to, and why."""

    provider: AIProviderType
    cli: Optional[str] = None
    connection_id: Optional[str] = None
    reason: str = ""


@dataclass
class AIExecutionSuccess(Generic[T]):
    """Successful AI execution result. Mirrors `ClientSuccess`'s shape."""

    decision: AIRouteDecision
    data: T
    message: str = ""


@dataclass
class AIExecutionError:
    """
    Failed AI execution result. Mirrors `ClientError`'s shape.

    `decision` may still be set (e.g. a provider was chosen but its
    execution failed, as opposed to no compatible provider being found).
    """

    error_message: str
    error_code: Optional[str] = None
    log_level: str = "error"
    details: Optional[dict] = None
    decision: Optional[AIRouteDecision] = None


# Usage: AIExecutionResult[AIResponse], AIExecutionResult[HeadlessResponse], etc.
AIExecutionResult = AIExecutionSuccess[T] | AIExecutionError


__all__ = [
    "AIExecutionRequest",
    "AIRoutePolicy",
    "AIRouteDecision",
    "AIExecutionSuccess",
    "AIExecutionError",
    "AIExecutionResult",
]
