"""
AI execution routing layer.

Unified decision layer for routing AI requests across remote providers
(AIClient/LiteLLM), CLI headless adapters, CLI interactive, and structured
remote responses. Per D-001, the router is a cross-cutting policy engine, not
a plugin's external-service client, so it does not follow the plugin 5-layer
pattern but mirrors ClientResult's success/error shape for consistency.
"""

from .availability import AIAvailabilityChecker, AIProviderAvailability
from .enums import AICapability, AIProviderType, AITask
from .models import (
    AIExecutionError,
    AIExecutionRequest,
    AIExecutionResult,
    AIExecutionSuccess,
    AIRouteDecision,
    AIRoutePolicy,
)
from .resolver import AIRouteNeedsInput, AIRouteResolution, AIRouteResolver

__all__ = [
    "AITask",
    "AICapability",
    "AIProviderType",
    "AIExecutionRequest",
    "AIRoutePolicy",
    "AIRouteDecision",
    "AIExecutionSuccess",
    "AIExecutionError",
    "AIExecutionResult",
    "AIAvailabilityChecker",
    "AIProviderAvailability",
    "AIRouteResolver",
    "AIRouteNeedsInput",
    "AIRouteResolution",
]
