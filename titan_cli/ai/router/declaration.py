"""
Self-declaration mechanism for steps that use AI.

`declare_ai_usage` is a decorator any step function - official or
community/third-party plugin - can attach to itself to announce "this step
uses AI" without registering anywhere central. A discovery service can later
scan registered workflows, resolve each step to its callable, and read this
attribute back off the function object.

Declaring usage (`ai_policy`) is informational only. Whether the step's
runtime behavior actually respects the resolved provider - i.e. whether it
calls `AIRouteResolver.resolve()` internally - is a separate claim, tracked
via `enforces`. A step can declare without enforcing.
"""

from typing import Callable, List, Optional, Set, TypeVar

from .enums import AICapability, AIProviderType
from .models import AIRoutePolicy

StepFunc = TypeVar("StepFunc", bound=Callable)

# Attribute names used to stash the declaration on the function object.
AI_POLICY_ATTR = "ai_policy"
AI_ENFORCES_ATTR = "ai_enforces"


def declare_ai_usage(
    task: str,
    capabilities: Optional[Set[AICapability]] = None,
    preferred: Optional[List[AIProviderType]] = None,
    strict: bool = False,
    remember: str = "ask",
    enforces: bool = False,
) -> Callable[[StepFunc], StepFunc]:
    """
    Attach an `AIRoutePolicy` to a step function so discovery can find it.

    Args:
        task: Routing/preference-persistence key. Reuse an `AITask` member
            for official plugins; community plugins may pass their own string.
        capabilities: Capabilities this step's AI usage requires.
        preferred: Provider types to try first, in order.
        strict: If True, only capability-satisfying providers may be used.
        remember: Default remember behavior ("ask" | "always" | "never").
        enforces: Set True only if the step's own code actually consults
            `AIRouteResolver`/`ctx.ai_router` at runtime, not just
            informational self-declaration. Defaults to False so
            undeclared/unmigrated steps never overstate what they guarantee.

    Returns:
        A decorator that stashes the policy on the function and returns it
        unchanged (no wrapping - the function still runs exactly as before).
    """

    def decorator(func: StepFunc) -> StepFunc:
        setattr(
            func,
            AI_POLICY_ATTR,
            AIRoutePolicy(
                task=task,
                capabilities=capabilities or set(),
                preferred=preferred or [],
                strict=strict,
                remember=remember,
            ),
        )
        setattr(func, AI_ENFORCES_ATTR, enforces)
        return func

    return decorator


def get_declared_ai_policy(func: Callable) -> Optional[AIRoutePolicy]:
    """Read back a step function's declared `AIRoutePolicy`, if any."""
    return getattr(func, AI_POLICY_ATTR, None)


def declared_ai_usage_enforces(func: Callable) -> bool:
    """Whether a step's own code actually enforces its declared policy."""
    return bool(getattr(func, AI_ENFORCES_ATTR, False))


__all__ = [
    "declare_ai_usage",
    "get_declared_ai_policy",
    "declared_ai_usage_enforces",
]
