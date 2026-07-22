"""
Route resolution for the AI execution routing layer.

Resolves which provider a task/workflow should use given persisted
preferences (`titan_cli.core.models.AIPreferences`) and provider availability
(`AIAvailabilityChecker`). Never picks a fallback silently: if a persisted
preference's provider is unavailable, resolution reports that user input is
needed instead of guessing, regardless of how many compatible candidates
remain. Strict capability enforcement (`AIRoutePolicy.strict`) is accepted as
input but not yet enforced - no per-provider capability matrix exists in code
yet, only in documentation.

No workflow calls this resolver yet - it exists so a future migration phase
has something to call.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set

from titan_cli.core.models import AIConfig, AIProviderPreference

from .availability import AIAvailabilityChecker, AIProviderAvailability
from .enums import AICapability, AIProviderType
from .models import AIRouteDecision, AIRoutePolicy


@dataclass
class AIRouteNeedsInput:
    """
    Resolution could not pick a provider automatically.

    Returned when no preference exists yet, or a persisted preference's
    provider became unavailable. Callers should ask the user; no ask-UI
    exists yet, so callers currently just surface this state.
    """

    reason: str
    candidates: List[AIProviderAvailability] = field(default_factory=list)


AIRouteResolution = AIRouteDecision | AIRouteNeedsInput


class AIRouteResolver:
    """Resolves which provider a task/workflow should use, given persisted preferences."""

    def __init__(self, ai_config: Optional[AIConfig], availability: AIAvailabilityChecker):
        self.ai_config = ai_config
        self.availability = availability

    def resolve(
        self,
        task: str,
        workflow_name: Optional[str] = None,
        policy: Optional[AIRoutePolicy] = None,
        capabilities: Optional[Set[AICapability]] = None,
        runtime_override: Optional[AIProviderType] = None,
    ) -> AIRouteResolution:
        """
        Resolve a provider following this precedence:
        runtime override -> persisted workflow preference -> persisted task
        preference -> workflow YAML default -> ask the user (no silent
        fallback). Strict step/workflow capability requirements are the
        caller's responsibility to have already narrowed `capabilities`
        with; this method does not filter candidates by capability.
        """
        capabilities = capabilities or set()

        if runtime_override is not None:
            if self.availability.is_provider_available(runtime_override):
                return AIRouteDecision(provider=runtime_override, reason="runtime override")
            return AIRouteNeedsInput(
                reason=f"runtime override '{runtime_override}' is not available",
                candidates=self._candidates(),
            )

        preferences = self._preferences()

        if preferences and workflow_name and workflow_name in preferences.workflows:
            resolved = self._resolve_preference(
                preferences.workflows[workflow_name],
                reason=f"workflow preference for '{workflow_name}'",
            )
            if resolved is not None:
                return resolved

        if preferences and task in preferences.tasks:
            resolved = self._resolve_preference(
                preferences.tasks[task],
                reason=f"task preference for '{task}'",
            )
            if resolved is not None:
                return resolved

        if policy and policy.preferred:
            for provider in policy.preferred:
                if self.availability.is_provider_available(provider):
                    return AIRouteDecision(provider=provider, reason=f"workflow YAML default '{provider}'")

        return AIRouteNeedsInput(
            reason="no persisted preference and no available workflow default",
            candidates=self._candidates(),
        )

    def _preferences(self):
        if not self.ai_config or not self.ai_config.preferences:
            return None
        return self.ai_config.preferences

    def _candidates(self) -> List[AIProviderAvailability]:
        return (
            self.availability.available_remote_connections()
            + self.availability.available_headless_clis()
            + self.availability.available_interactive_clis()
        )

    def _resolve_preference(
        self, pref: AIProviderPreference, reason: str
    ) -> Optional[AIRouteResolution]:
        """
        Try to honor a persisted preference.

        Returns `AIRouteDecision` if its exact provider/cli/connection_id is
        available, `AIRouteNeedsInput` if unavailable (never a silent
        fallback, even if `pref.fallback` is set or a *different* candidate
        of the same provider type happens to be available), or `None` if the
        preference's provider value doesn't map to a known `AIProviderType`
        (caller should keep checking lower-precedence sources).
        """
        try:
            provider = AIProviderType(pref.provider)
        except ValueError:
            return None

        if self._identifier_available(provider, pref.cli or pref.connection_id):
            return AIRouteDecision(
                provider=provider,
                cli=pref.cli,
                connection_id=pref.connection_id,
                reason=reason,
            )

        return AIRouteNeedsInput(
            reason=f"{reason} is no longer available ('{pref.provider}')",
            candidates=self._candidates(),
        )

    def _identifier_available(self, provider: AIProviderType, identifier: Optional[str]) -> bool:
        """
        Whether `provider` is available and, if `identifier` (a specific CLI
        name or connection ID) is given, whether that exact candidate is
        among the available ones - not just any candidate of that provider
        type.
        """
        if provider == AIProviderType.CLI_HEADLESS:
            candidates = self.availability.available_headless_clis()
        elif provider == AIProviderType.CLI_INTERACTIVE:
            candidates = self.availability.available_interactive_clis()
        elif provider in (AIProviderType.REMOTE, AIProviderType.REMOTE_STRUCTURED):
            candidates = self.availability.available_remote_connections()
        elif provider == AIProviderType.OFF:
            return True
        else:
            return False

        if identifier is None:
            return bool(candidates)
        return any(candidate.identifier == identifier for candidate in candidates)


__all__ = ["AIRouteResolver", "AIRouteNeedsInput", "AIRouteResolution"]
